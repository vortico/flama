import asyncio
import dataclasses
import logging
import time
import typing as t
import uuid

from flama import exceptions, types
from flama.models.engine.llm.decoder.decoder import Decoder, _ResolvedDecoder
from flama.models.engine.llm.decoder.markers import Scanner, _Event, _EventKind
from flama.models.engine.llm.delta import EngineDelta
from flama.models.transport.input.llm.shape.base import Shape
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent

__all__ = ["LLMCodec"]

if t.TYPE_CHECKING:
    from flama.models.base import LLMModel

logger = logging.getLogger(__name__)

PREFLIGHT_PROMPT: t.Final[str] = "Hi"
PREFLIGHT_MAX_TOKENS: t.Final[int] = 256
PREFLIGHT_MAX_CHARS: t.Final[int] = 4096

_State: t.TypeAlias = t.Literal["outside", "channel", "tool"]
_Source: t.TypeAlias = t.Literal["channel", "tool"]


class _FSM:
    """Decoder state machine: scans the buffer and dispatches transitions.

    Three explicit literal states (:data:`_State`) describe the FSM's structural position.
    Channel state is held inline as ``_channel: str`` (no separate object). A one-deep
    "previous state" memory (``_previous_state``) lets ``"tool"`` return to whichever state
    opened it, so a model that emits a tool inside a channel resumes the channel afterwards.

    The FSM consumes a fully-resolved :class:`Decoder` (no ``None`` slots): :class:`LLMCodec`
    runs detection and provides the resolved configuration before constructing the FSM, so the
    state machine never has to perform any selection of its own.

    The FSM is also the canonical authority on the run-level stop reason. It latches each
    delta's engine-native ``finish_reason`` and counts the tool calls it emits via
    :meth:`_action_exit_tool`; :meth:`terminate` then composes both pieces into the canonical
    :class:`~flama.models.transport.output.llm.event.StopEvent`. ``"tool_use"`` requires the
    conjunction ``engine reported clean stop`` AND ``at least one tool call was emitted``,
    and the FSM is the only place in the pipeline where both ingredients are visible at once
    (engines like MLX never surface ``finish_reason``; tool detection lives in the scanner).

    :param decoder: Fully-resolved decoder configuration.
    """

    _Action: t.TypeAlias = t.Callable[["_FSM", _Event, str], t.Iterable[Event]]

    _FINISH_REASON_MAP: t.ClassVar[dict[str, types.LLMTransportStopReason]] = {
        "stop": "stop",
        "length": "max_tokens",
        "tool_calls": "tool_use",
    }

    def __init__(self, decoder: _ResolvedDecoder, /) -> None:
        self._decoder = decoder
        self._buffer: str = ""
        self._tool_buffer: str = ""
        self._state: _State = "outside"
        self._previous_state: tuple[_State, str | None] = ("outside", decoder.policy.output)
        self._channel: str | None = decoder.policy.output
        self._tool_count: int = 0
        self._engine_reason: str | None = None

    def feed(self, delta: EngineDelta, /) -> t.Iterator[Event]:
        """Process one backend delta: scan text, latch engine metadata, emit events.

        On a delta carrying ``finish_reason``, the FSM is flushed before the terminal trace is
        yielded so consumers never observe content blocks after a stream-terminating trace.
        """
        if delta.text:
            self._buffer += delta.text
            while self._buffer:
                scanned = self._scan()
                if scanned is None:
                    break
                event, source = scanned
                slice_, self._buffer = self._buffer[: event.length], self._buffer[event.length :]
                yield from self._transition(event, source, slice_)
        if delta.finish_reason is not None:
            self._engine_reason = delta.finish_reason
            yield from self.flush()
        if delta.token_count is not None or delta.finish_reason is not None:
            yield TraceEvent(token_count=delta.token_count, finish_reason=delta.finish_reason)

    def flush(self) -> t.Iterator[Event]:
        """Emit any remaining buffered text and drain the tool parser at EOS.

        Idempotent: a second call after the buffer has already been drained is a no-op
        because ``self._buffer`` is empty and the state has already returned to ``"outside"``.
        """
        if self._buffer:
            text, self._buffer = self._buffer, ""
            if self._state == "tool":
                self._tool_buffer += text
            else:
                yield TextEvent(channel=self._channel, text=text)
        if self._state == "tool":
            yield from self._action_exit_tool(_Event(kind="close", length=0), "")

    def terminate(self, output_tokens: int, /) -> StopEvent:
        """Mint the canonical lifecycle :class:`StopEvent` for this run.

        Composes the latched engine-native ``finish_reason`` with the tool-emission count so
        ``"tool_use"`` surfaces correctly even on backends that report only ``"stop"`` (vLLM,
        whose tokeniser doesn't know about per-template tool markers) or report nothing at all
        (MLX). The decision rule is linear: an unset engine reason canonicalises from FSM state
        alone; otherwise the mapped value is promoted to ``"tool_use"`` whenever the FSM
        observed at least one tool call.
        """
        if self._engine_reason is None:
            stop_reason = "tool_use" if self._tool_count > 0 else "stop"
        else:
            mapped = self._FINISH_REASON_MAP.get(self._engine_reason)
            if mapped is None:
                logger.warning("Unmapped backend finish_reason %r (classified as 'unknown')", self._engine_reason)
                stop_reason = "unknown"
            elif mapped == "stop" and self._tool_count > 0:
                stop_reason = "tool_use"
            else:
                stop_reason = mapped
        return StopEvent(stop_reason=stop_reason, output_tokens=output_tokens)

    def _scan(self) -> tuple[_Event, _Source] | None:
        """Pick the next ``(event, source)`` pair from the head of the buffer.

        Both scanners run in lockstep when the FSM is outside any tool body. If either active
        scanner returns :data:`None` the entire buffer is held until more input arrives -
        otherwise a partial marker prefix could be wrongly emitted as content by the
        passthrough on the other side. When both report an event the candidate with the
        smallest leading content slice wins (a length-0 marker beats any content); tool wins
        on ties because the iteration is reversed before :func:`min` (stable-min keeps the
        last-seen candidate, and tool is appended last).
        """
        decoder = self._decoder
        sources: list[tuple[Scanner, _Source, bool]] = (
            [(decoder.tool_scanner, "tool", True)]
            if self._state == "tool"
            else [(decoder.channel_scanner, "channel", self._state == "channel"), (decoder.tool_scanner, "tool", False)]
        )

        candidates: list[tuple[_Event, _Source]] = []
        for scanner, source, inside in sources:
            event = scanner.scan(self._buffer, inside=inside)
            if event is None:
                return None
            candidates.append((event, source))
        return min(reversed(candidates), key=lambda c: c[0].length if c[0].kind == "content" else 0)

    def _transition(self, event: _Event, source: _Source, slice_: str) -> t.Iterator[Event]:
        """Single dispatch on ``(state, kind, source)``; all FSM rules live in :data:`_TRANSITIONS`."""
        if (handler := self._TRANSITIONS.get((self._state, event.kind, source))) is None:
            return
        yield from handler(self, event, slice_)

    def _action_emit_text(self, event: _Event, slice_: str) -> t.Iterable[Event]:
        return [TextEvent(channel=self._channel, text=slice_)] if slice_ else ()

    def _action_enter_channel(self, event: _Event, slice_: str) -> t.Iterable[Event]:
        self._previous_state = (self._state, self._channel)
        self._channel = self._decoder.policy.resolve(event.channel)
        self._state = "channel"
        return ()

    def _action_leave_channel(self, event: _Event, slice_: str) -> t.Iterable[Event]:
        self._state, self._channel = self._previous_state
        self._previous_state = ("outside", self._decoder.policy.output)
        return ()

    def _action_enter_tool(self, event: _Event, slice_: str) -> t.Iterable[Event]:
        self._previous_state = (self._state, self._channel)
        self._state = "tool"
        return ()

    def _action_buffer_tool(self, event: _Event, slice_: str) -> t.Iterable[Event]:
        self._tool_buffer += slice_
        return ()

    def _action_exit_tool(self, event: _Event, slice_: str) -> t.Iterator[Event]:
        body, self._tool_buffer = self._tool_buffer, ""
        parser = self._decoder.tool_parser
        for call in parser.parse(body):
            self._tool_count += 1
            yield ToolEvent(id=str(uuid.uuid4()), name=call.name, arguments=call.arguments)
        self._state, self._channel = self._previous_state
        self._previous_state = ("outside", self._decoder.policy.output)

    def _action_consume_close(self, event: _Event, slice_: str) -> t.Iterable[Event]:
        # Strip a stray close literal whose paired open the FSM never saw (e.g. Gemma 4's prompt-prefix empty
        # channel pair). The slice has already been removed from the buffer by `feed`; the action just suppresses
        # any text emission so the literal bytes don't surface to the user.
        return ()

    _TRANSITIONS: t.ClassVar[dict[tuple[_State, _EventKind, _Source], _Action]] = {
        ("outside", "content", "channel"): _action_emit_text,
        ("outside", "content", "tool"): _action_emit_text,
        ("outside", "open", "channel"): _action_enter_channel,
        ("outside", "open", "tool"): _action_enter_tool,
        ("outside", "close", "channel"): _action_consume_close,
        ("outside", "close", "tool"): _action_consume_close,
        ("channel", "content", "channel"): _action_emit_text,
        ("channel", "content", "tool"): _action_emit_text,
        ("channel", "close", "channel"): _action_leave_channel,
        ("channel", "open", "tool"): _action_enter_tool,
        ("channel", "close", "tool"): _action_consume_close,
        ("tool", "content", "tool"): _action_buffer_tool,
        ("tool", "close", "tool"): _action_exit_tool,
    }


class LLMCodec:
    """Per-model orchestrator that wraps a :class:`Decoder` config.

    Holds a single :attr:`decoder` reference plus an :class:`asyncio.Lock` guarding warmup detection. Detection
    itself lives on :class:`Decoder`; this class drives the three-stage cascade in :meth:`detect`: a pinned
    decoder is used verbatim, otherwise the chat-template sample is tried alone (cheap), and preflight runs only
    as a last resort.

    Internal - constructed by :class:`~flama.models.base.LLMModel` from a user-supplied :class:`Decoder` (or
    :data:`None`).

    :param decoder: Decoder configuration to wrap, or :data:`None` to auto-detect everything.
    """

    def __init__(self, decoder: Decoder | None, preflight_prompt: str = PREFLIGHT_PROMPT) -> None:
        self._decoder = decoder or Decoder()
        self._resolved_decoder: _ResolvedDecoder | None = None
        self._preflight_prompt = preflight_prompt
        self._lock = asyncio.Lock()
        # Backend-agnostic fallback used when a delta arrives without a backend-supplied token
        # count (e.g. older MLX runtimes that don't expose ``generation_tokens``). Populated in
        # :meth:`detect` from the bound model's tokenizer; kept as ``None`` when detection has
        # not run yet or the backend lacks a usable :meth:`encode` primitive.
        self._count_tokens: t.Callable[[str], int] | None = None

    @property
    def decoder(self) -> _ResolvedDecoder:
        """Return the resolved decoder set by :meth:`detect`; raise if detection has not run yet."""
        if self._resolved_decoder is None:
            raise exceptions.ApplicationError("Decoder is not detected.")

        return self._resolved_decoder

    @decoder.setter
    def decoder(self, decoder: _ResolvedDecoder, /) -> None:
        self._resolved_decoder = decoder

    @decoder.deleter
    def decoder(self) -> None:
        self._resolved_decoder = None

    async def detect(self, model: "LLMModel", /) -> None:
        """Run the three-stage detection cascade and store the resolved decoder.

        Idempotent and concurrency-safe: only the first call performs detection. The stages are:

        1.  **Pinned**: if every slot on the spec is already a concrete instance
            (:attr:`Decoder.is_resolved`), wrap them in a :class:`_ResolvedDecoder` directly - no I/O.
        2.  **Template-only**: fetch the rendered chat-template sample and call :meth:`Decoder._try_resolve`. If
            every slot is detected from the template alone, preflight is skipped.
        3.  **Template + preflight**: run preflight and call :meth:`Decoder.resolve`, which substitutes the
            corresponding passthrough sentinel for any slot that remains unrecognised.

        Any failure on a side falls back to the corresponding passthrough so application startup never aborts on
        decoder selection.
        """
        async with self._lock:
            if self._resolved_decoder is not None:
                return

            decoder = self._decoder.resolve(default=False)
            if decoder is None:
                template = self._chat_template_sample(model) or ""
                decoder = self._decoder.resolve(template, default=False)
                if decoder is None:
                    sample = await self._preflight(model) or ""
                    decoder = self._decoder.resolve(template, sample, default=True)

            self.decoder = decoder

            logger.info(
                "Decoder detected: channel_scanner=%s tool_scanner=%s tool_parser=%s",
                decoder.channel_scanner.name,
                decoder.tool_scanner.name,
                decoder.tool_parser.name,
            )

            if decoder.tool_parser.name == "passthrough" and decoder.tool_scanner.name != "passthrough":
                logger.warning(
                    "Tool parser fell back to 'passthrough' (scanner=%s) and tool calls won't be dispatched",
                    decoder.tool_scanner.name,
                )

            # Capture the backend's tokenizer once detection is settled so :meth:`decode` can
            # recover ``token_count`` for backends that ship text without a count (older MLX
            # text/vlm runtimes). The lambda closes over ``encode`` rather than ``model`` so the
            # codec doesn't anchor a strong reference to the model lifecycle.
            encode = getattr(model.backend, "encode", None)
            if callable(encode):
                self._count_tokens = lambda text: len(encode(text, add_special_tokens=False))

    async def decode(
        self,
        stream: t.AsyncIterator[EngineDelta],
        *,
        message_id: uuid.UUID | None = None,
        input_tokens: int | None = None,
    ) -> t.AsyncIterator[Event]:
        """Consume *stream* and yield :class:`Event` events with surrounding lifecycle markers.

        When *message_id* is supplied the iterator opens with a :class:`StartEvent` (carrying *message_id*, the
        current wall-clock timestamp, and *input_tokens*) and closes with the canonical :class:`StopEvent`
        produced by :meth:`_FSM.terminate`. The FSM owns the run-level ``stop_reason`` decision because it has
        visibility into both engine-native ``finish_reason`` signals (latched per delta) and content-level
        :class:`ToolEvent` emissions (counted in :meth:`_FSM._action_exit_tool`); promoting ``"stop"`` to
        ``"tool_use"`` when tool calls were emitted is therefore a single linear rule on the FSM rather than a
        bookkeeping pass at this layer. Exceptions propagate without a synthetic stop marker — the driver layer
        owns the ``"error"`` envelope so callers can record per-stream usage observed up to that point.

        Pass ``message_id=None`` to bypass lifecycle entirely (used by tests and internal one-off decodes that
        don't feed a stream buffer).

        The post-loop :meth:`_FSM.flush` is a safety net for streams that omit ``finish_reason``; when
        ``finish_reason`` was seen, ``feed`` already flushed and the post-loop call is a no-op.

        :param stream: Async iterator of backend deltas.
        :param message_id: Optional stream identifier surfaced in the opening :class:`StartEvent`.
        :param input_tokens: Optional prompt token count surfaced in the opening :class:`StartEvent` and the
            terminal :class:`StopEvent` usage snapshot.
        """
        started = time.monotonic()
        if message_id is not None:
            decoder = self.decoder
            logger.debug(
                "LLM run start: id=%s input_tokens=%s channel_scanner=%s tool_scanner=%s tool_parser=%s",
                message_id,
                input_tokens,
                decoder.channel_scanner.name,
                decoder.tool_scanner.name,
                decoder.tool_parser.name,
            )
            yield StartEvent(id=str(message_id), created=int(time.time()), input_tokens=input_tokens)

        fsm = _FSM(self.decoder)
        output_tokens = 0
        async for delta in stream:
            if delta.token_count is None and delta.text and self._count_tokens is not None:
                try:
                    inferred = self._count_tokens(delta.text)
                except Exception as exc:
                    logger.debug("Token-count fallback raised %s; leaving delta count unset", exc)
                else:
                    delta = dataclasses.replace(delta, token_count=inferred)
            logger.debug(
                "LLM delta: text=%r token_count=%s finish_reason=%s",
                delta.text,
                delta.token_count,
                delta.finish_reason,
            )
            for event in fsm.feed(delta):
                logger.debug("LLM event: %s", event)
                yield event
            output_tokens += delta.token_count or 0
        for event in fsm.flush():
            logger.debug("LLM event (flush): %s", event)
            yield event

        if message_id is not None:
            stop = fsm.terminate(output_tokens)
            logger.debug(
                "LLM run done: id=%s input_tokens=%s output_tokens=%d stop_reason=%s tool_calls=%d elapsed_ms=%.1f",
                message_id,
                input_tokens,
                output_tokens,
                stop.stop_reason,
                fsm._tool_count,
                (time.monotonic() - started) * 1000,
            )
            yield stop

    def _chat_template_sample(self, model: "LLMModel", /) -> str | None:
        """Pull a rendered chat-template sample off the bound backend."""
        try:
            return model.backend.chat_template_sample()
        except Exception as exc:
            logger.warning("Backend chat-template introspection failed (%s)", exc)
            return None

    async def _preflight(self, model: "LLMModel") -> str | None:
        """Render a tiny prompt and collect a few tokens of output."""
        try:
            inputs = await Shape.build("chat", prompt=self._preflight_prompt).render(model.backend)
        except Exception:
            return None

        sample = ""
        try:
            async for delta in model.backend.generate(inputs, max_tokens=PREFLIGHT_MAX_TOKENS):
                if not delta.text:
                    continue
                sample += delta.text
                if len(sample) >= PREFLIGHT_MAX_CHARS:
                    break
        except Exception as exc:
            logger.warning("Channel-scanner preflight failed (%s)", exc)
            return None

        return sample
