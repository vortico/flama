import json
import typing as t

from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.transport.input.llm.message import (
    Content,
    ImageFormat,
    ImageURI,
    ImageURL,
    Message,
    SourceURI,
    SourceURL,
    TextContent,
)
from flama.models.transport.input.llm.tool import Tool
from flama.models.wire.dialect.base import Parser

__all__ = ["AnthropicParser"]

_ACCEPTED_PARTS: t.Final[tuple[str, ...]] = (
    "text",
    "image",
    "tool_use",
    "tool_result",
    "thinking",
    "redacted_thinking",
)
_ANTHROPIC_TO_IMAGE_FORMAT: t.Final[dict[str, ImageFormat]] = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/gif": "gif",
    "image/webp": "webp",
}


class AnthropicParser(Parser):
    """Anthropic-compatible wire parser (L1 -> L2).

    Owns every wire-translation step the Anthropic Messages API needs:

    - :meth:`_parse_messages` flattens the optional top-level ``system`` payload into a leading
      :class:`~flama.models.SystemMessage`, expands user turns carrying ``tool_result`` blocks into one
      canonical ``tool`` message per result (Anthropic packs them into a single user turn; Flama's L2
      ``tool`` messages take a single ``tool_call_id`` each), and splits assistant turns into the
      canonical ``content`` / ``tool_calls`` / ``reasoning_content`` triple.
    - :meth:`_parse_tool` consumes Anthropic's flat ``{name, description, input_schema}`` shape (no
      OpenAI-style ``function:`` envelope).
    - :meth:`_parse_part` translates ``text`` / ``image`` parts only; ``tool_use`` / ``tool_result`` /
      ``thinking`` / ``redacted_thinking`` are split off by :meth:`_parse_messages` before they reach
      the part level, so seeing one here is a wire violation surfaced as
      :class:`LLMUnsupportedContentPart`.
    """

    @classmethod
    def _parse_messages(
        cls,
        values: list[dict[str, t.Any]],
        /,
        *,
        system: t.Any = None,
    ) -> tuple[Message, ...]:
        out: list[Message] = []
        if (system_text := cls._flatten_system(system)) is not None:
            out.append(cls._parse_message({"role": "system", "content": system_text}))

        for raw in values:
            if not isinstance(raw, dict):
                raise ValueError("messages element must be an object")
            match raw.get("role"):
                case "user":
                    out.extend(cls._parse_message(turn) for turn in cls._expand_user(raw.get("content")))
                case "assistant":
                    out.append(cls._parse_message(cls._expand_assistant(raw.get("content"))))
                case role:
                    raise ValueError(f"Wrong role {role!r}, expected one of: ['user', 'assistant']")
        return tuple(out)

    @classmethod
    def _parse_tool(cls, value: t.Any) -> Tool:
        """Translate an Anthropic ``tools`` element (``{name, description, input_schema}``) into a canonical
        :class:`Tool`. The Anthropic shape has no ``type`` / ``function:`` envelope, so the OpenAI-style
        base parser cannot consume it directly.
        """
        if not isinstance(value, dict):
            raise ValueError("tools element must be an object")
        return Tool(
            name=value.get("name"),
            description=value.get("description"),
            parameters=value.get("input_schema", {}),
        )

    @classmethod
    def _parse_part(cls, part: t.Any) -> Content:  # noqa: C901
        if not isinstance(part, dict) or "type" not in part:
            raise ValueError("content parts must be objects with a 'type' field")
        match part["type"]:
            case "text":
                text = part.get("text")
                if not isinstance(text, str):
                    raise ValueError("text content parts must carry a string 'text' field")
                return TextContent(text=text)
            case "image":
                source = part.get("source")
                if not isinstance(source, dict) or "type" not in source:
                    raise ValueError("'image' content parts must carry a 'source' object with a 'type' field")
                source_type = source["type"]
                if source_type == "base64":
                    data = source.get("data")
                    media_type = source.get("media_type")
                    if not isinstance(data, str) or not isinstance(media_type, str):
                        raise ValueError("'image' base64 sources must carry a 'data' string and a 'media_type' string")
                    fmt = _ANTHROPIC_TO_IMAGE_FORMAT.get(media_type.lower())
                    if fmt is None:
                        raise ValueError(
                            f"Wrong image media_type {media_type!r}, expected one of: "
                            f"{sorted(_ANTHROPIC_TO_IMAGE_FORMAT)}"
                        )
                    return ImageURI(source=SourceURI.parse(data), format=fmt)
                if source_type == "url":
                    url = source.get("url")
                    if not isinstance(url, str):
                        raise ValueError("'image' url sources must carry a 'url' string")
                    return ImageURL(source=SourceURL.parse(url))
                raise ValueError(f"Wrong image source type {source_type!r}, expected one of: ['base64', 'url']")
            case kind:
                raise LLMUnsupportedContentPart(kind, _ACCEPTED_PARTS)

    @classmethod
    def _flatten_system(cls, system: t.Any, /) -> str | None:
        """Collapse Anthropic's ``system`` field into a single string.

        Anthropic accepts ``str`` or ``list[{type, text}]``; both shapes flatten to a single string the
        caller injects as a leading system message. Empty / unsupported shapes return ``None`` so the
        caller can skip the system turn entirely.
        """
        if system is None:
            return None
        if isinstance(system, str):
            return system or None
        if isinstance(system, list):
            parts: list[str] = []
            for block in system:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            return "".join(parts) or None
        return None

    @classmethod
    def _expand_user(cls, content: t.Any, /) -> list[dict[str, t.Any]]:
        """Expand a user turn into a sequence of canonical ``tool`` and / or ``user`` turns.

        Anthropic packs all tool results from a single agent step into one ``user`` turn carrying multiple
        ``tool_result`` content blocks. The canonical L2 schema only allows one ``tool_call_id`` per
        ``tool`` turn, so each ``tool_result`` block expands into its own ``tool`` turn; non-tool content
        parts (``text`` / ``image``) collect into a residual user turn (when any).
        """
        if isinstance(content, str):
            return [{"role": "user", "content": content}] if content else []
        if not isinstance(content, list):
            raise ValueError("user 'content' must be a string or a list of content blocks")

        out: list[dict[str, t.Any]] = []
        residual: list[t.Any] = []
        for block in content:
            if not isinstance(block, dict) or "type" not in block:
                raise ValueError("user content blocks must be objects with a 'type' field")
            if block["type"] == "tool_result":
                tool_use_id = block.get("tool_use_id")
                if not isinstance(tool_use_id, str):
                    raise ValueError("'tool_result' blocks must carry a 'tool_use_id' string")
                out.append(
                    {
                        "role": "tool",
                        "content": cls._tool_result_text(block.get("content")),
                        "tool_call_id": tool_use_id,
                    }
                )
            else:
                residual.append(block)

        if residual:
            out.append({"role": "user", "content": residual})
        return out

    @classmethod
    def _expand_assistant(cls, content: t.Any, /) -> dict[str, t.Any]:  # noqa: C901
        """Split an assistant turn's ``content`` blocks into Flama's canonical ``content`` / ``tool_calls`` /
        ``reasoning_content`` triple.
        """
        if isinstance(content, str):
            return {"role": "assistant", "content": content}
        if not isinstance(content, list):
            raise ValueError("assistant 'content' must be a string or a list of content blocks")

        text_parts: list[t.Any] = []
        tool_calls: list[dict[str, t.Any]] = []
        thinking_parts: list[str] = []
        for block in content:
            if not isinstance(block, dict) or "type" not in block:
                raise ValueError("assistant content blocks must be objects with a 'type' field")
            match block["type"]:
                case "text":
                    text_parts.append(block)
                case "tool_use":
                    tool_calls.append(
                        {
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(block.get("input", {})),
                            },
                        }
                    )
                case "thinking":
                    thinking = block.get("thinking")
                    if isinstance(thinking, str):
                        thinking_parts.append(thinking)
                case "redacted_thinking":
                    continue
                case kind:
                    raise ValueError(
                        f"Wrong assistant content block {kind!r}, "
                        f"expected one of: ['text', 'tool_use', 'thinking', 'redacted_thinking']"
                    )

        out: dict[str, t.Any] = {"role": "assistant"}
        if text_parts:
            out["content"] = text_parts
        if tool_calls:
            out["tool_calls"] = tool_calls
        if thinking_parts:
            out["reasoning_content"] = "".join(thinking_parts)
        if "content" not in out and "tool_calls" not in out:
            out["content"] = ""
        return out

    @classmethod
    def _tool_result_text(cls, value: t.Any, /) -> str:
        """Flatten a ``tool_result`` ``content`` payload into a plain string for the canonical ``tool`` turn.

        Anthropic accepts either a string or a list of typed blocks (typically ``text``); both flatten to a
        single concatenated string. Non-text blocks (``image`` / unsupported types) JSON-encode their
        payload so the tool result is never dropped.
        """
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for block in value:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block, dict):
                    parts.append(json.dumps(block))
            return "".join(parts)
        if value is None:
            return ""
        return json.dumps(value)
