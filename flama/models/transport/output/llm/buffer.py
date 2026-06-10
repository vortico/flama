import collections
import logging
import typing as t

from flama import concurrency
from flama.exceptions import FrameworkNotInstalled
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent

if t.TYPE_CHECKING:
    from flama.models.wire.dialect._base import Renderer

__all__ = ["EventBuffer"]

logger = logging.getLogger(__name__)

_T = t.TypeVar("_T")


class EventBuffer(t.Generic[_T]):
    """L2 FSM engine: drives an :class:`Event` source through a
    :class:`~flama.models.wire.dialect._base.Renderer` strategy.

    Owns: source consumption (via :func:`flama.concurrency.iterate`), error pump (synthesises a
    :class:`StopEvent` with ``stop_reason='error'`` on framework / generic failures), lifecycle capture
    (exposed via :attr:`start` and :attr:`stop` post-consumption), skip-counted suppression of leading outputs,
    and dispatch to :class:`~flama.models.wire.dialect._base.Renderer` ``on_<kind>`` methods.

    Sources can be any synchronous or asynchronous iterable of events (lists, generators,
    :class:`~flama.models.streams.StreamBuffer`). The constructor normalises them via
    :func:`flama.concurrency.iterate`, which yields through async iterables directly and drives sync iterables
    off the event loop via a bounded queue.

    Exceptions raised by the source iterator during consumption are intercepted: a synthesised
    :class:`StopEvent` with ``stop_reason='error'`` is dispatched through the renderer and the iterator
    terminates cleanly. :class:`FrameworkNotInstalled` is logged at ``error`` level without traceback;
    every other exception goes through :meth:`logging.Logger.exception`.

    The leading-output suppression count is read from :attr:`Renderer.skip` (default ``0``). Resume-aware
    renderers set this on construction so the engine drops already-delivered frames; the engine itself does
    not expose a separate ``skip`` parameter.

    :param source: Sync or async iterable of events.
    :param renderer: Strategy translating events to outputs of type ``_T``.
    """

    def __init__(
        self,
        source: t.Iterable[Event] | t.AsyncIterable[Event],
        renderer: "Renderer[_T]",
        /,
    ) -> None:
        self._source = concurrency.iterate(source)
        self._renderer = renderer
        self._skip = renderer.skip
        self._pending: collections.deque[_T] = collections.deque()
        self._emitted = 0
        self._exhausted = False
        self._start: StartEvent | None = None
        self._stop: StopEvent | None = None

    @property
    def start(self) -> StartEvent:
        """Opening lifecycle marker captured during iteration.

        :raises RuntimeError: If accessed before the buffer has been fully consumed.
        """
        if self._start is None:
            raise RuntimeError("Buffer must be consumed before accessing `start`")
        return self._start

    @property
    def stop(self) -> StopEvent:
        """Terminal lifecycle marker captured during iteration.

        :raises RuntimeError: If accessed before the buffer has been fully consumed.
        """
        if self._stop is None:
            raise RuntimeError("Buffer must be consumed before accessing `stop`")
        return self._stop

    def __aiter__(self) -> "EventBuffer[_T]":
        return self

    async def __anext__(self) -> _T:
        while not self._pending:
            if self._exhausted:
                raise StopAsyncIteration
            try:
                block = await self._source.__anext__()
            except StopAsyncIteration:
                self._exhausted = True
                self._pending.extend(self._renderer.flush())
                if not self._pending:
                    raise
                continue
            except FrameworkNotInstalled as exc:
                logger.error("Stream backend missing dependency: %s", exc)
                block = StopEvent(stop_reason="error")
                self._exhausted = True
            except Exception as exc:
                logger.exception("Stream generation failed: %s", exc)
                block = StopEvent(stop_reason="error")
                self._exhausted = True

            if isinstance(block, StartEvent):
                self._start = block
            elif isinstance(block, StopEvent):
                self._stop = block
            self._dispatch(block)
            while self._pending and self._emitted < self._skip:
                self._pending.popleft()
                self._emitted += 1
        self._emitted += 1
        return self._pending.popleft()

    def _dispatch(self, block: Event) -> None:
        """Route *block* to its typed ``on_<kind>`` renderer method, calling :meth:`flush` before stop."""
        match block:
            case StartEvent():
                self._pending.extend(self._renderer.on_start(block))
            case TextEvent():
                self._pending.extend(self._renderer.on_text(block))
            case ToolEvent():
                self._pending.extend(self._renderer.on_tool(block))
            case TraceEvent():
                self._pending.extend(self._renderer.on_trace(block))
            case StopEvent():
                self._pending.extend(self._renderer.flush())
                self._pending.extend(self._renderer.on_stop(block))

    async def assemble(self) -> tuple[_T, ...]:
        """Drain the buffer and return the assembled outputs as a tuple."""
        return tuple([item async for item in self])
