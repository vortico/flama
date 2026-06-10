import typing as t

from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.transport.input.llm.message import (
    Content,
    ImageFormat,
    ImageURI,
    ImageURL,
    SourceURI,
    SourceURL,
    TextContent,
)
from flama.models.wire.dialect._base import Parser

__all__ = ["OllamaParser"]


class OllamaParser(Parser):
    """Ollama-compatible wire parser (L1 -> L2).

    Handles Ollama's wire quirk of carrying images as a sibling ``images: [...]`` field on chat messages;
    :meth:`_canonicalize_message` pre-splices that list into canonical structured ``content`` parts before
    the shared parsing skeleton runs, so downstream code sees a uniform shape.
    """

    _ACCEPTED_PARTS: t.Final[tuple[str, ...]] = ("text", "image:url", "image:uri")

    @classmethod
    def _canonicalize_message(cls, value: t.Any, /) -> t.Any:
        """Adapt Ollama's native multimodal shape to canonical structured ``content`` parts.

        Ollama's ``/api/chat`` carries images as a sibling ``images: list[base64-string]`` field with a
        plain-string ``content``. Flama's transport / backend pipeline expects canonical structured
        parts (a list of ``{"type":"text",...}`` / ``{"type":"image:uri",...}`` entries). When the
        message has a non-empty ``images`` array, each base64 payload is spliced into an
        ``image:uri`` part (``data:`` URIs are split into raw base64 plus a format hint), with the
        original text prepended as a text part; the ``images`` field is then dropped so downstream
        code sees a uniform canonical payload.

        Idempotent on messages without an ``images`` field; non-dict inputs pass through unchanged.
        """
        if not isinstance(value, dict):
            return value
        images = value.get("images")
        if not images or not isinstance(images, list):
            return value
        original_content = value.get("content")
        parts: list[dict[str, t.Any]] = []
        if isinstance(original_content, str) and original_content:
            parts.append({"type": "text", "text": original_content})
        for image in images:
            if not isinstance(image, str) or not image:
                continue
            if image.startswith("data:"):
                fmt = cls._format_from_data_uri(image, allowed=cls.IMAGE_FORMATS, default="png")
                _, _, raw = image.partition(",")
                parts.append({"type": "image:uri", "data": raw, "format": fmt})
            else:
                parts.append({"type": "image:uri", "data": image, "format": "png"})
        normalized = {k: v for k, v in value.items() if k != "images"}
        normalized["content"] = parts
        return normalized

    @classmethod
    def _parse_part(cls, part: t.Any) -> Content:
        if not isinstance(part, dict) or "type" not in part:
            raise ValueError("content parts must be objects with a 'type' field")
        match part["type"]:
            case "text":
                text = part.get("text")
                if not isinstance(text, str):
                    raise ValueError("text content parts must carry a string 'text' field")
                return TextContent(text=text)
            case "image:url":
                url = part.get("url")
                if not isinstance(url, str):
                    raise ValueError("'image:url' content parts must carry a 'url' string")
                return ImageURL(source=SourceURL.parse(url))
            case "image:uri":
                data = part.get("data")
                fmt_value = part.get("format")
                if not isinstance(data, str) or not isinstance(fmt_value, str):
                    raise ValueError("'image:uri' content parts must carry a 'data' string and a 'format' string")
                return ImageURI(source=SourceURI.parse(data), format=t.cast(ImageFormat, fmt_value))
            case kind:
                raise LLMUnsupportedContentPart(kind, cls._ACCEPTED_PARTS)
