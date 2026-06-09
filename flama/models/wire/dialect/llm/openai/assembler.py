import json
import string
import typing as t
import uuid

from flama import compat, types
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect.base import Assembler

__all__ = ["OpenAIAssembleKwargs", "OpenAIAssembler"]


class OpenAIAssembleKwargs(t.TypedDict, total=False):
    """Per-stream kwargs accepted by :class:`OpenAIAssembler.envelope` (and so by :meth:`Dialect.assemble`).

    ``api`` and ``model`` are required; ``generation_id`` carries a sensible default.
    """

    api: compat.Required[t.Literal["chat", "completion", "response"]]
    model: compat.Required[str]
    generation_id: uuid.UUID | None


class OpenAIAssembler(Assembler):
    """L2 -> OpenAI buffered envelope strategy.

    Dispatches on the *api* discriminator: ``"chat"`` -> ``chat.completion``; ``"completion"`` ->
    ``text_completion``; ``"response"`` -> Responses API ``response`` envelope. Buffered envelopes are
    JSON-serialisable dicts ready for :class:`~flama.http.responses.api.APIResponse`.
    """

    _STOP_REASON_TO_OPENAI: t.Final[dict[types.LLMTransportStopReason, str]] = {
        "stop": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
        "content_filter": "content_filter",
        "cancelled": "stop",
        "error": "stop",
        "unknown": "stop",
    }
    _EVENT_ID_TEMPLATE: t.Final[string.Template] = string.Template("$prefix-$message_id")
    _KIND_PREFIX: t.Final[dict[t.Literal["chat", "completion", "response"], str]] = {
        "chat": "chatcmpl",
        "completion": "cmpl",
        "response": "resp",
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
        **kwargs: compat.Unpack[OpenAIAssembleKwargs],
    ) -> dict[str, t.Any]:
        api = kwargs["api"]
        model = kwargs["model"]
        generation_id = kwargs.get("generation_id")
        if api == "chat":
            return cls._chat(events, start=start, stop=stop, model=model, generation_id=generation_id)
        if api == "completion":
            return cls._completion(events, start=start, stop=stop, model=model, generation_id=generation_id)
        return cls._response(events, start=start, stop=stop, model=model, generation_id=generation_id)

    @staticmethod
    def _chat(
        events: tuple[Event, ...],
        *,
        start: StartEvent,
        stop: StopEvent,
        model: str,
        generation_id: uuid.UUID | None,
    ) -> dict[str, t.Any]:
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[dict[str, t.Any]] = []
        for block in events:
            match block:
                case TextEvent(channel="output") if block.text:
                    text_parts.append(block.text)
                case TextEvent() if block.text:
                    reasoning_parts.append(block.text)
                case ToolEvent() if block.name:
                    tool_calls.append(
                        {
                            "id": block.id,
                            "type": "function",
                            "function": {"name": block.name, "arguments": json.dumps(block.arguments)},
                        }
                    )

        content = "".join(text_parts)
        reasoning_content = "".join(reasoning_parts)
        message: dict[str, t.Any] = {
            "role": "assistant",
            "content": content or None,
            "reasoning_content": reasoning_content or None,
            "tool_calls": tool_calls or None,
        }

        input_tokens = start.input_tokens or 0
        output_tokens = stop.output_tokens or 0
        return {
            "id": OpenAIAssembler._event_id("chat", generation_id),
            "object": "chat.completion",
            "created": start.created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": OpenAIAssembler._STOP_REASON_TO_OPENAI.get(stop.stop_reason or "stop", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    @staticmethod
    def _completion(
        events: tuple[Event, ...], *, start: StartEvent, stop: StopEvent, model: str, generation_id: uuid.UUID | None
    ) -> dict[str, t.Any]:
        text_parts: list[str] = [b.text for b in events if isinstance(b, TextEvent) and b.channel == "output"]
        finish_reason = OpenAIAssembler._STOP_REASON_TO_OPENAI.get(stop.stop_reason or "stop", "stop")
        input_tokens = start.input_tokens or 0
        output_tokens = stop.output_tokens or 0
        return {
            "id": OpenAIAssembler._event_id("completion", generation_id),
            "object": "text_completion",
            "created": start.created,
            "model": model,
            "choices": [{"index": 0, "text": "".join(text_parts), "finish_reason": finish_reason}],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    @staticmethod
    def _response(
        events: tuple[Event, ...],
        *,
        start: StartEvent,
        stop: StopEvent,
        model: str,
        generation_id: uuid.UUID | None,
    ) -> dict[str, t.Any]:
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        output: list[dict[str, t.Any]] = []
        for block in events:
            match block:
                case TextEvent(channel="output") if block.text:
                    text_parts.append(block.text)
                case TextEvent() if block.text:
                    reasoning_parts.append(block.text)
                case ToolEvent() if block.name:
                    output.append(
                        {
                            "id": block.id,
                            "type": "function_call",
                            "call_id": block.id,
                            "name": block.name,
                            "arguments": json.dumps(block.arguments),
                        }
                    )

        text = "".join(text_parts)
        reasoning_text = "".join(reasoning_parts)
        if text:
            output.insert(
                0,
                {
                    "id": "msg_0",
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                },
            )
        if reasoning_text:
            output.insert(
                0,
                {
                    "id": "reasoning_0",
                    "type": "reasoning",
                    "status": "completed",
                    "summary": [{"type": "summary_text", "text": reasoning_text}],
                },
            )

        input_tokens = start.input_tokens or 0
        output_tokens = stop.output_tokens or 0
        return {
            "id": OpenAIAssembler._event_id("response", generation_id),
            "object": "response",
            "created_at": start.created,
            "status": "completed",
            "model": model,
            "output": output,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    @classmethod
    def _event_id(cls, api: t.Literal["chat", "completion", "response"], generation_id: uuid.UUID | None, /) -> str:
        return cls._EVENT_ID_TEMPLATE.safe_substitute(
            {"prefix": cls._KIND_PREFIX[api], "message_id": (generation_id or uuid.uuid4()).hex}
        )
