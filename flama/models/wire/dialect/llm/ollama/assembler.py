import typing as t
from datetime import datetime, timezone

from flama import compat, types
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect._base import Assembler

__all__ = ["OllamaAssembleKwargs", "OllamaAssembler"]


class OllamaAssembleKwargs(t.TypedDict, total=False):
    """Per-stream kwargs accepted by :class:`OllamaAssembler.envelope`."""

    api: compat.Required[t.Literal["chat", "generate"]]
    model: compat.Required[str]


class OllamaAssembler(Assembler):
    """L2 -> Ollama buffered envelope strategy.

    Dispatches on the *api* discriminator: ``"chat"`` -> ``/api/chat`` envelope; ``"generate"`` ->
    ``/api/generate`` envelope. Both share a common terminal shape stamping ``done: true``,
    ``done_reason``, and the running ``prompt_eval_count`` / ``eval_count`` totals captured from the start
    and stop lifecycle markers.
    """

    _STOP_REASON_TO_OLLAMA: t.Final[dict[types.LLMTransportStopReason, str]] = {
        "stop": "stop",
        "max_tokens": "length",
        "tool_use": "stop",
        "content_filter": "stop",
        "cancelled": "stop",
        "error": "stop",
        "unknown": "stop",
    }

    @classmethod
    # Concrete envelopes deliberately require dialect identity kwargs (``api``/``model``), so they narrow the
    # base ``**kwargs: Any`` to a TypedDict-unpacked signature. That strengthening is intentional and not LSP.
    def envelope(  # ty: ignore[invalid-method-override]
        cls,
        events: tuple[Event, ...],
        /,
        *,
        start: StartEvent,
        stop: StopEvent,
        **kwargs: compat.Unpack[OllamaAssembleKwargs],
    ) -> dict[str, t.Any]:
        api = kwargs["api"]
        model = kwargs["model"]
        if api == "chat":
            return cls._chat(events, start=start, stop=stop, model=model)
        return cls._generate(events, start=start, stop=stop, model=model)

    @staticmethod
    def _chat(events: tuple[Event, ...], *, start: StartEvent, stop: StopEvent, model: str) -> dict[str, t.Any]:
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[dict[str, t.Any]] = []
        for block in events:
            match block:
                case TextEvent(channel="output"):
                    text_parts.append(block.text)
                case TextEvent():
                    thinking_parts.append(block.text)
                case ToolEvent():
                    tool_calls.append({"function": {"name": block.name, "arguments": block.arguments}})

        message: dict[str, t.Any] = {"role": "assistant", "content": "".join(text_parts)}
        if thinking_parts:
            message["thinking"] = "".join(thinking_parts)
        if tool_calls:
            message["tool_calls"] = tool_calls
        return {
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "done": True,
            "done_reason": OllamaAssembler._STOP_REASON_TO_OLLAMA.get(stop.stop_reason or "stop", "stop"),
            "prompt_eval_count": start.input_tokens or 0,
            "eval_count": stop.output_tokens or 0,
        }

    @staticmethod
    def _generate(events: tuple[Event, ...], *, start: StartEvent, stop: StopEvent, model: str) -> dict[str, t.Any]:
        text_parts = [b.text for b in events if isinstance(b, TextEvent) and b.channel == "output"]
        return {
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "response": "".join(text_parts),
            "done": True,
            "done_reason": OllamaAssembler._STOP_REASON_TO_OLLAMA.get(stop.stop_reason or "stop", "stop"),
            "prompt_eval_count": start.input_tokens or 0,
            "eval_count": stop.output_tokens or 0,
        }
