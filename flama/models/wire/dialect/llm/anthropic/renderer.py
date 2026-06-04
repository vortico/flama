import json
import string
import time
import typing as t
import uuid

from flama import types
from flama._core.json_encoder import encode_json
from flama.http.responses.sse import ServerSentEvent
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect.base import Renderer

__all__ = ["AnthropicRenderer"]


class AnthropicRenderer(Renderer[ServerSentEvent]):
    """L2 -> Anthropic Messages API SSE strategy.

    Drives the Messages API streaming FSM: a ``message_start`` envelope opens the message, each output
    content is opened with ``content_block_start`` / streamed with ``content_block_delta`` / closed with
    ``content_block_stop``, the terminal usage and ``stop_reason`` ride on a ``message_delta``, and the
    stream is sealed with a ``message_stop``. Tool-use blocks emit ``input_json_delta`` chunks carrying
    a single full ``partial_json`` payload (Flama emits complete tool calls atomically; clients that
    accumulate the partial JSON re-build the same object). Off-output (``thinking``) channel text opens
    a parallel ``thinking`` content block driven by ``thinking_delta`` events; redacted-thinking blocks
    are not surfaced (Flama never emits the upstream signature path).

    :param model: Model identifier echoed on every ``message_start`` envelope.
    :param generation_id: Optional generation UUID anchoring the ``msg_`` envelope id; a fresh one is
        allocated when omitted.
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

    def __init__(self, *, model: str, generation_id: uuid.UUID | None = None) -> None:
        self._model = model
        self._id = AnthropicRenderer._event_id(generation_id)
        self._created = int(time.time())
        self._block_index = -1
        self._text_open = False
        self._thinking_open = False
        self._message_started = False
        self._input_tokens = 0
        self._output_tokens = 0

    @classmethod
    def _event_id(cls, generation_id: uuid.UUID | None, /) -> str:
        return cls._EVENT_ID_TEMPLATE.safe_substitute({"message_id": (generation_id or uuid.uuid4()).hex})

    def _frame(self, type_: str, payload: dict[str, t.Any], /) -> ServerSentEvent:
        return ServerSentEvent(event=type_, data=encode_json({"type": type_, **payload}, compact=True).decode())

    def _ensure_message_start(self) -> t.Iterable[ServerSentEvent]:
        if self._message_started:
            return
        self._message_started = True
        yield self._frame(
            "message_start",
            {
                "message": {
                    "id": self._id,
                    "type": "message",
                    "role": "assistant",
                    "model": self._model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": self._input_tokens, "output_tokens": 0},
                }
            },
        )

    def on_start(self, block: StartEvent) -> t.Iterable[ServerSentEvent]:
        self._input_tokens = block.input_tokens or 0
        yield from self._ensure_message_start()

    def on_text(self, block: TextEvent) -> t.Iterable[ServerSentEvent]:
        if not block.text:
            return
        yield from self._ensure_message_start()
        if block.channel == "output":
            yield from self._close_thinking()
            yield from self._open_text()
            yield self._frame(
                "content_block_delta",
                {"index": self._block_index, "delta": {"type": "text_delta", "text": block.text}},
            )
            return
        yield from self._close_text()
        yield from self._open_thinking()
        yield self._frame(
            "content_block_delta",
            {"index": self._block_index, "delta": {"type": "thinking_delta", "thinking": block.text}},
        )

    def on_tool(self, block: ToolEvent) -> t.Iterable[ServerSentEvent]:
        if not block.name:
            return
        yield from self._ensure_message_start()
        yield from self._close_text()
        yield from self._close_thinking()
        self._block_index += 1
        index = self._block_index
        yield self._frame(
            "content_block_start",
            {
                "index": index,
                "content_block": {"type": "tool_use", "id": block.id, "name": block.name, "input": {}},
            },
        )
        partial = json.dumps(block.arguments)
        yield self._frame(
            "content_block_delta",
            {"index": index, "delta": {"type": "input_json_delta", "partial_json": partial}},
        )
        yield self._frame("content_block_stop", {"index": index})

    def on_stop(self, block: StopEvent) -> t.Iterable[ServerSentEvent]:
        yield from self._ensure_message_start()
        yield from self._close_text()
        yield from self._close_thinking()
        if block.stop_reason == "error":
            yield self._frame(
                "error",
                {"error": {"type": "api_error", "message": "LLM stream generation failed"}},
            )
        self._output_tokens = block.output_tokens or self._output_tokens
        stop_reason = (
            self._STOP_REASON_TO_ANTHROPIC.get(block.stop_reason, "end_turn") if block.stop_reason else "end_turn"
        )
        yield self._frame(
            "message_delta",
            {
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"input_tokens": self._input_tokens, "output_tokens": self._output_tokens},
            },
        )
        yield self._frame("message_stop", {})

    def flush(self) -> t.Iterable[ServerSentEvent]:
        return ()

    def _open_text(self) -> t.Iterable[ServerSentEvent]:
        if self._text_open:
            return
        self._block_index += 1
        self._text_open = True
        yield self._frame(
            "content_block_start",
            {"index": self._block_index, "content_block": {"type": "text", "text": ""}},
        )

    def _close_text(self) -> t.Iterable[ServerSentEvent]:
        if not self._text_open:
            return
        yield self._frame("content_block_stop", {"index": self._block_index})
        self._text_open = False

    def _open_thinking(self) -> t.Iterable[ServerSentEvent]:
        if self._thinking_open:
            return
        self._block_index += 1
        self._thinking_open = True
        yield self._frame(
            "content_block_start",
            {"index": self._block_index, "content_block": {"type": "thinking", "thinking": ""}},
        )

    def _close_thinking(self) -> t.Iterable[ServerSentEvent]:
        if not self._thinking_open:
            return
        yield self._frame("content_block_stop", {"index": self._block_index})
        self._thinking_open = False
