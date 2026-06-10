import string
import typing as t
import uuid

from flama import compat, types
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect._base import Assembler

__all__ = ["AnthropicAssembleKwargs", "AnthropicAssembler"]


class AnthropicAssembleKwargs(t.TypedDict, total=False):
    """Per-stream kwargs accepted by :class:`AnthropicAssembler.envelope`.

    ``model`` is required; ``generation_id`` carries a sensible default (a fresh UUID is allocated when
    omitted).
    """

    model: compat.Required[str]
    generation_id: uuid.UUID | None


class AnthropicAssembler(Assembler):
    """L2 -> Anthropic Messages API buffered envelope strategy.

    Drains the coalesced :class:`~flama.models.Event` tuple into a Messages API ``message`` envelope:
    a ``content`` array carrying ordered ``thinking`` / ``text`` / ``tool_use`` blocks, the terminal
    ``stop_reason`` (mapped from Flama's transport stop reasons), and the request / response token usage.
    """

    _STOP_REASON_TO_ANTHROPIC: t.Final[dict[types.LLMTransportStopReason, str]] = {
        "stop": "end_turn",
        "max_tokens": "max_tokens",
        "tool_use": "tool_use",
        "content_filter": "end_turn",
        "cancelled": "end_turn",
        "error": "end_turn",
        "unknown": "end_turn",
    }
    _EVENT_ID_TEMPLATE: t.Final[string.Template] = string.Template("msg_$message_id")

    @classmethod
    # Concrete envelopes deliberately require dialect identity kwargs (``model``), so they narrow the base
    # ``**kwargs: Any`` to a TypedDict-unpacked signature. That strengthening is intentional and not LSP.
    def envelope(  # ty: ignore[invalid-method-override]
        cls,
        events: tuple[Event, ...],
        /,
        *,
        start: StartEvent,
        stop: StopEvent,
        **kwargs: compat.Unpack[AnthropicAssembleKwargs],
    ) -> dict[str, t.Any]:
        model = kwargs["model"]
        generation_id = kwargs.get("generation_id")
        content: list[dict[str, t.Any]] = []
        thinking_parts: list[str] = []
        text_parts: list[str] = []
        for block in events:
            match block:
                case TextEvent(channel="output") if block.text:
                    text_parts.append(block.text)
                case TextEvent() if block.text:
                    thinking_parts.append(block.text)
                case ToolEvent() if block.name:
                    if thinking_parts:
                        content.append({"type": "thinking", "thinking": "".join(thinking_parts)})
                        thinking_parts = []
                    if text_parts:
                        content.append({"type": "text", "text": "".join(text_parts)})
                        text_parts = []
                    content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.arguments,
                        }
                    )

        if thinking_parts:
            content.append({"type": "thinking", "thinking": "".join(thinking_parts)})
        if text_parts:
            content.append({"type": "text", "text": "".join(text_parts)})

        stop_reason = (
            cls._STOP_REASON_TO_ANTHROPIC.get(stop.stop_reason or "stop", "end_turn")
            if stop.stop_reason
            else "end_turn"
        )
        return {
            "id": cls._event_id(generation_id),
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": start.input_tokens or 0,
                "output_tokens": stop.output_tokens or 0,
            },
        }

    @classmethod
    def _event_id(cls, generation_id: uuid.UUID | None, /) -> str:
        return cls._EVENT_ID_TEMPLATE.safe_substitute({"message_id": (generation_id or uuid.uuid4()).hex})
