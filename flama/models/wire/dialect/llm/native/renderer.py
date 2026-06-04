import re
import string
import typing as t
import uuid

from flama._core.json_encoder import encode_json
from flama.http.responses.sse import ServerSentEvent
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent
from flama.models.wire.dialect.base import Renderer

__all__ = ["EventsRenderer"]

_RendererState: t.TypeAlias = t.Literal["idle", "text", "tool"]


class EventsRenderer(Renderer[ServerSentEvent]):
    """L2 -> native SSE strategy.

    Emits the dot-notation ``<message_id>.<sequence>`` SSE id format the native dialect invented for
    ``Last-Event-ID``-driven resume. Holds per-stream identity (``message_id``, monotonic sequence counter)
    plus the FSM state (open block index, channel, running usage totals) directly on the instance; no
    separate state object is required.

    Each fed block can produce zero or more frames (a :class:`~flama.models.TextEvent` channel transition
    emits ``block.stop`` then ``block.start`` then ``block.delta``). Lifecycle blocks translate to their wire
    frames so a cold-stored log can be replayed verbatim, with :class:`StopEvent(stop_reason="error")`
    injecting an ``error`` frame before the terminal ``message.stop``. On source exhaustion any open block is
    flushed with a closing ``block.stop`` before :class:`StopAsyncIteration` propagates.

    Resume handling lives in :meth:`__init__`: when *resume_id* parses successfully **and** its embedded
    message id matches *message_id*, the embedded sequence seeds both the renderer's monotonic counter (so
    the next emitted frame's id continues where the client left off) and the engine's :attr:`skip` count (so
    already delivered frames are suppressed). Mismatched, malformed, or absent *resume_id* values fall back
    to a fresh state at sequence ``0``.

    :cvar USAGE_FLUSH_TOKENS: Throttle threshold; a ``message.delta`` carrying running usage is flushed every
        time at least this many output tokens have accumulated since the last flush.

    :param message_id: Stable identifier for the generation (the buffer uuid). Anchors the SSE id format.
    :param resume_id: Optional ``Last-Event-ID`` header value carried over a reconnect.
    :param retry: Optional retry hint stamped on the opening ``message.start`` frame for SSE auto-reconnect.
    """

    USAGE_FLUSH_TOKENS: t.ClassVar[int] = 32
    _EVENT_ID_PATTERN: t.Final[re.Pattern[str]] = re.compile(
        r"^(?P<message_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}).(?P<sequence>\d+)$"
    )
    _EVENT_ID_TEMPLATE: t.Final[string.Template] = string.Template("$message_id.$sequence")

    def __init__(self, *, message_id: uuid.UUID, resume_id: str | None = None, retry: int | None = None) -> None:
        self._message_id = message_id
        self._sequence = 0
        self._retry = retry
        self.skip = self._parse_event_id(resume_id, message_id=message_id) or 0
        self._index = -1
        self._fsm_state: _RendererState = "idle"
        self._channel: str | None = None
        self._input_tokens = 0
        self._output_tokens = 0
        self._unflushed_tokens = 0
        self._finish_reason: str | None = None

    @classmethod
    def _parse_event_id(cls, value: str | None, /, *, message_id: uuid.UUID) -> int | None:
        """Decode the dot-notation ``<message_id>.<sequence>`` SSE id into typed parts.

        Used by :meth:`EventsRenderer.resume` to recover client position from a ``Last-Event-ID`` header. The
        inverse direction (encoding the next id from the renderer's running counter) lives inline on
        :meth:`EventsRenderer._next_id`.

        :returns: Sequence number if matches, otherwise None.
        """
        if (
            value
            and (match := cls._EVENT_ID_PATTERN.match(value))
            and message_id == uuid.UUID(match.group("message_id"))
        ):
            return int(match.group("sequence"))

    def _next_id(self) -> str:
        self._sequence += 1
        return self._EVENT_ID_TEMPLATE.safe_substitute({"message_id": self._message_id, "sequence": self._sequence})

    def _frame(self, event: str, body: dict[str, t.Any], /, *, retry: int | None = None) -> ServerSentEvent:
        sse = ServerSentEvent(
            event=event,
            id=self._next_id(),
            data=encode_json(body, compact=True).decode(),
        )
        if retry is not None:
            sse.retry = retry
        return sse

    def on_start(self, block: StartEvent) -> t.Iterable[ServerSentEvent]:
        if block.input_tokens is not None:
            self._input_tokens = block.input_tokens
        yield self._frame(
            "message.start",
            {"type": "message.start", "id": block.id, "created": block.created},
            retry=self._retry,
        )

    def _block_descriptor(self, block: TextEvent | ToolEvent, /) -> dict[str, t.Any]:
        descriptor = block.payload()
        descriptor.pop("text", None)
        if descriptor.get("type") == "tool":
            descriptor["arguments"] = {}
        return descriptor

    def on_text(self, block: TextEvent) -> t.Iterable[ServerSentEvent]:
        if self._fsm_state != "text" or self._channel != block.channel:
            yield from self.flush()
            self._index += 1
            self._fsm_state = "text"
            self._channel = block.channel
            yield self._frame(
                "block.start",
                {
                    "type": "block.start",
                    "index": self._index,
                    "block": self._block_descriptor(TextEvent(channel=block.channel, text="")),
                },
            )
        if block.text:
            yield self._frame(
                "block.delta",
                {"type": "block.delta", "index": self._index, "delta": block.delta_payload()},
            )

    def on_tool(self, block: ToolEvent) -> t.Iterable[ServerSentEvent]:
        yield from self.flush()
        self._index += 1
        self._fsm_state = "tool"
        yield self._frame(
            "block.start",
            {"type": "block.start", "index": self._index, "block": self._block_descriptor(block)},
        )
        yield self._frame(
            "block.delta",
            {"type": "block.delta", "index": self._index, "delta": block.delta_payload()},
        )

    def on_trace(self, block: TraceEvent) -> t.Iterable[ServerSentEvent]:
        if block.token_count is not None and block.token_count > 0:
            self._output_tokens += block.token_count
            self._unflushed_tokens += block.token_count
        if block.finish_reason is not None:
            self._finish_reason = block.finish_reason
        if self._unflushed_tokens >= self.USAGE_FLUSH_TOKENS:
            self._unflushed_tokens = 0
            yield self._frame(
                "message.delta",
                {"type": "message.delta", "output_tokens": self._output_tokens},
            )

    def on_stop(self, block: StopEvent) -> t.Iterable[ServerSentEvent]:
        if block.stop_reason == "error":
            yield self._frame(
                "error",
                {"type": "error", "status": 500, "detail": "LLM stream generation failed"},
            )
        body: dict[str, t.Any] = {"type": "message.stop"}
        if block.stop_reason is not None:
            body["stop_reason"] = block.stop_reason
        if block.output_tokens is not None:
            body["output_tokens"] = block.output_tokens
        yield self._frame("message.stop", body)

    def flush(self) -> t.Iterable[ServerSentEvent]:
        if self._fsm_state != "idle":
            yield self._frame(
                "block.stop",
                {"type": "block.stop", "index": self._index},
            )
        self._fsm_state = "idle"
        self._channel = None
