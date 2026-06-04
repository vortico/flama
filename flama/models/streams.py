import abc
import asyncio
import collections
import contextlib
import dataclasses
import json
import logging
import pathlib
import shutil
import tempfile
import time
import typing as t
import uuid

from flama import concurrency, types
from flama._core.json_encoder import encode_json
from flama.exceptions import FrameworkNotInstalled
from flama.models.transport.output.llm.event import Event, StopEvent, TraceEvent

__all__ = [
    "StreamsBackend",
    "FileStreamsBackend",
    "InMemoryStreamsBackend",
    "CleanupTask",
    "StreamsRegistry",
    "ModelStreams",
    "StreamBuffer",
]


DEFAULT_EPHEMERAL_CAPACITY: t.Final[int] = 64

logger = logging.getLogger(__name__)


class StreamsBackend(abc.ABC):
    """Cold-storage transport for stream events.

    Persists :class:`~flama.models.Event` events keyed by ``(model, response_id)`` and exposes range reads by
    line index. Owns its own lifecycle independently of the registry orchestrating it. Implementations include
    :class:`FileStreamsBackend` (JSONL on disk); future backends could target Redis, S3, or Postgres without
    requiring changes to :class:`StreamsRegistry`.

    Both :meth:`aopen` and :meth:`aclose` are idempotent so the registry can call them repeatedly under varying
    lifecycle conditions (tests reusing a backend, modules re-binding to an app).
    """

    def __len__(self) -> int:
        return sum(self.length().values())

    async def aopen(self) -> None:
        """Initialise the backend. Idempotent."""
        ...

    async def aclose(self) -> None:
        """Release backend resources. Idempotent."""
        ...

    @abc.abstractmethod
    def length(self) -> dict[tuple[str, uuid.UUID], int]:
        """Per-stream block count snapshot, keyed by ``(model, key)``."""
        ...

    @abc.abstractmethod
    async def append(self, model: str, key: uuid.UUID, block: Event) -> None:
        """Persist *block* to the durable log identified by ``(model, key)``.

        :param model: Per-model namespace (e.g. the LLM resource name).
        :param key: Per-response identifier.
        :param block: Event to persist (any :class:`Event` subclass).
        """
        ...

    @abc.abstractmethod
    async def read(self, model: str, key: uuid.UUID, start: int, end: int) -> list[Event]:
        """Read events in the half-open line range ``[start, end)`` from the durable log.

        Non-destructive: subsequent reads of the same range yield the same blocks. Returns ``[]`` for indices
        the backend cannot serve (never written, already :meth:`pop`-ed, or out of range).

        :param model: Per-model namespace.
        :param key: Per-response identifier.
        :param start: Inclusive line index.
        :param end: Exclusive line index.
        :return: Rehydrated :class:`Event` instances ordered by line index.
        """
        ...

    @abc.abstractmethod
    async def pop(self, model: str, key: uuid.UUID, start: int, end: int) -> list[Event]:
        """Read-and-remove events in the half-open absolute-index range ``[start, end)``.

        Destructive variant of :meth:`read`: returned blocks are removed from the backend so capacity-bounded
        implementations can free space for new writes (and unblock backpressured producers). Backends that
        treat their storage as durable and indivisible (e.g. :class:`FileStreamsBackend`) MAY implement this as
        a non-destructive no-op delegate to :meth:`read`; the contract is that the *caller's* logical view of
        the indices in ``[start, end)`` is consumed once.

        Should also notify any producers suspended on full capacity that space may now be available.

        :param model: Per-model namespace.
        :param key: Per-response identifier.
        :param start: Inclusive line index.
        :param end: Exclusive line index.
        :return: Rehydrated :class:`Event` instances ordered by line index.
        """
        ...

    @abc.abstractmethod
    async def discard(self, model: str, key: uuid.UUID) -> None:
        """Drop the durable log identified by ``(model, key)``.

        :param model: Per-model namespace (e.g. the LLM resource name).
        :param key: Per-response identifier.
        """
        ...

    @abc.abstractmethod
    def usage(self) -> dict[tuple[str, uuid.UUID], int] | None:
        """Per-stream storage usage in bytes (or ``None`` if not measurable).

        Backends that cannot cheaply report usage (e.g. ephemeral in-memory transports) return ``None``;
        :class:`CleanupTask` ignores such backends for the disk-usage policy without raising.

        :return: ``{(model, key): bytes_used}`` snapshot or ``None``.
        """
        ...


class FileStreamsBackend(StreamsBackend):
    """JSONL-on-disk cold-storage backend.

    Each ``(model, key)`` pair maps to ``<root>/<model>/<key>.jsonl``: an append-only stream of tagged JSON
    envelopes (one per line) produced by :meth:`Event.to_dict`. A per-stream line-offset index makes slicing by
    line index ``O(slice_size)`` without rescanning the file, and doubles as the source for :meth:`usage`.

    By default the backend owns a per-process tempdir (created lazily in :meth:`aopen` via
    :func:`tempfile.mkdtemp`, recursively removed in :meth:`aclose`). Passing an explicit ``path`` pins the
    backend to a fixed root (useful for tests or pre-allocated volumes); ``remove=False`` keeps that root
    after :meth:`aclose` so callers retain the JSONL logs for inspection.

    :param path: Optional fixed root path. When ``None`` a fresh tempdir is allocated on :meth:`aopen`.
    :param remove: When ``True`` (default) the root is recursively removed on :meth:`aclose`. Set to
        ``False`` to keep a pinned ``path`` across lifecycles (e.g. development).
    """

    def __init__(self, *, path: pathlib.Path | None = None, remove: bool = True) -> None:
        self._path = path
        self._remove = remove
        self._root: pathlib.Path | None = None
        self._writers: dict[tuple[str, uuid.UUID], t.IO[bytes]] = {}
        self._line_offsets: dict[tuple[str, uuid.UUID], list[int]] = {}

    @property
    def root(self) -> pathlib.Path:
        """Resolved root path. Available after :meth:`aopen`.

        :raises RuntimeError: If the backend has not been opened yet.
        """
        if self._root is None:
            raise RuntimeError("FileStreamsBackend is not open")
        return self._root

    def length(self) -> dict[tuple[str, uuid.UUID], int]:
        # ``_line_offsets`` stores ``N+1`` entries per stream (offsets of the ``N`` lines plus the trailing
        # byte offset that closes the last line), so the line count is ``len(offsets) - 1``.
        return {key: len(offsets) - 1 for key, offsets in self._line_offsets.items()}

    async def aopen(self) -> None:
        if self._root is None:
            self._root = (
                self._path if self._path is not None else pathlib.Path(tempfile.mkdtemp(prefix="flama-streams-"))
            )

            if not self._root.exists():
                await concurrency.run(self._root.mkdir, parents=True, exist_ok=True)
                self._root = self._path

    async def aclose(self) -> None:
        if self._root is not None:
            for fd in self._writers.values():
                await concurrency.run(fd.close)

            if self._remove:
                await concurrency.run(shutil.rmtree, self._root)

            self._writers.clear()
            self._line_offsets.clear()

            self._root = None

    async def append(self, model: str, key: uuid.UUID, block: Event) -> None:
        line = encode_json(block.to_dict(), compact=True) + b"\n"
        await concurrency.run(self._write_line, await self._writer(model, key), line)
        offsets = self._line_offsets[(model, key)]
        offsets.append(offsets[-1] + len(line))

    async def read(self, model: str, key: uuid.UUID, start: int, end: int) -> list[Event]:
        if (offsets := self._line_offsets.get((model, key))) is None or start >= end or end > len(offsets) - 1:
            return []

        data = bytearray()
        async with concurrency.FileReader(
            self._file_path(model, key), chunk_size=1 << 16, start=offsets[start], end=offsets[end]
        ) as reader:
            async for chunk in reader:
                data += chunk

        return [Event.from_dict(json.loads(line)) for line in data.splitlines() if line]

    async def pop(self, model: str, key: uuid.UUID, start: int, end: int) -> list[Event]:
        """Non-destructive equivalent to :meth:`read` for the on-disk log.

        The JSONL log is the durable record consumed by reconnecting clients (native SSE ``Last-Event-ID``
        replay), so popping individual lines would corrupt that record. Capacity is bounded by
        :class:`CleanupTask` instead, which evicts entire ``(model, key)`` logs via :meth:`discard`.
        """
        return await self.read(model, key, start, end)

    async def discard(self, model: str, key: uuid.UUID) -> None:
        if (fd := self._writers.pop((model, key), None)) is not None:
            await concurrency.run(fd.close)

        self._line_offsets.pop((model, key), None)

        await concurrency.run(self._file_path(model, key).unlink, missing_ok=True)

    def usage(self) -> "dict[tuple[str, uuid.UUID], int]":
        """Bytes written per stream, derived from the line-offset index."""
        return {key: offsets[-1] for key, offsets in self._line_offsets.items()}

    @staticmethod
    def _write_line(fd: t.IO[bytes], line: bytes) -> None:
        fd.write(line)
        fd.flush()

    def _file_path(self, model: str, key: uuid.UUID) -> pathlib.Path:
        return self.root / model / f"{str(key)}.jsonl"

    async def _writer(self, model: str, key: uuid.UUID) -> t.IO[bytes]:
        if (model, key) not in self._writers:
            path = self._file_path(model, key)
            await concurrency.run(path.parent.mkdir, parents=True, exist_ok=True)
            fd = t.cast(t.IO[bytes], await concurrency.run(open, path, "ab"))
            self._writers[(model, key)] = fd
            self._line_offsets[(model, key)] = [0]

        return self._writers[(model, key)]


class InMemoryStreamsBackend(StreamsBackend):
    """Ephemeral in-memory backend with optional bounded capacity and backpressure.

    Stores blocks in a per-key :class:`collections.deque`, tracking the absolute index of each block so reads
    and pops operate in the same index space as :class:`FileStreamsBackend` (the producer never sees indices
    shift). Two operating modes are controlled by ``capacity``:

    -   **Unbounded** (``capacity=None``): :meth:`append` never suspends, every block stays resident until
        explicitly popped or discarded. Suitable as the *only* storage for a buffer (e.g. ephemeral OpenAI
        chat-completion streams) when the protocol has a single in-process consumer.

    -   **Bounded** (``capacity>0``): :meth:`append` suspends on a per-key :class:`asyncio.Condition` when the
        deque is full, until :meth:`pop` (or :meth:`discard`) frees space. This realises producer-side
        backpressure: a slow consumer transparently slows the producer instead of dropping blocks. Suitable
        as the *hot/in-flight* tier paired with a durable backend (e.g. :class:`FileStreamsBackend`) on
        :class:`StreamBuffer`, where the durable backend serves any reads of indices that have already been
        popped.

    The deque holds at most ``capacity`` blocks at once but :meth:`length` reports the *total* number of
    blocks ever appended for a key, so absolute indices remain meaningful after eviction.

    :param capacity: Maximum number of blocks resident per ``(model, key)`` at any time. ``None`` (default)
        disables the bound; a positive integer enables backpressure.
    :raises ValueError: If ``capacity`` is non-positive.
    """

    def __init__(self, *, capacity: int | None = None) -> None:
        if capacity is not None and capacity <= 0:
            raise ValueError("InMemoryStreamsBackend `capacity` must be positive or None")
        self._capacity = capacity
        self._data: dict[tuple[str, uuid.UUID], collections.deque[Event]] = {}
        self._base: dict[tuple[str, uuid.UUID], int] = {}
        self._total: dict[tuple[str, uuid.UUID], int] = {}
        self._condition: asyncio.Condition = asyncio.Condition()

    @property
    def capacity(self) -> int | None:
        """Configured per-key capacity, or ``None`` for unbounded mode."""
        return self._capacity

    def length(self) -> dict[tuple[str, uuid.UUID], int]:
        """Total appends ever observed per key (does not shrink on :meth:`pop` or eviction)."""
        return dict(self._total)

    async def append(self, model: str, key: uuid.UUID, block: Event) -> None:
        """Append *block*; suspend on full capacity until :meth:`pop` frees a slot.

        In bounded mode the call blocks on the internal :class:`asyncio.Condition`. Producers therefore see
        backpressure without needing to coordinate explicitly; consumers drive the pace via :meth:`pop`.
        """
        async with self._condition:
            if self._capacity is not None:
                while len(self._data.get((model, key), ())) >= self._capacity:
                    await self._condition.wait()
            self._data.setdefault((model, key), collections.deque()).append(block)
            self._base.setdefault((model, key), 0)
            self._total[(model, key)] = self._total.get((model, key), 0) + 1
            self._condition.notify_all()

    async def read(self, model: str, key: uuid.UUID, start: int, end: int) -> list[Event]:
        """Return resident blocks in ``[start, end)`` without removing them."""
        if (dq := self._data.get((model, key))) is None or start >= end:
            return []
        base = self._base[(model, key)]
        local_start = max(0, start - base)
        local_end = max(0, end - base)
        if local_start >= len(dq) or local_end <= 0:
            return []
        return list(dq)[local_start : min(local_end, len(dq))]

    async def pop(self, model: str, key: uuid.UUID, start: int, end: int) -> list[Event]:
        """Read-and-remove resident blocks in ``[start, end)`` and wake suspended producers.

        Only the *prefix* of the requested range that still lives in the deque is removed; gaps caused by
        prior pops are returned as empty and must be fulfilled by another backend (the durable one on
        :class:`StreamBuffer`).
        """
        async with self._condition:
            if (dq := self._data.get((model, key))) is None or start >= end:
                return []
            base = self._base[(model, key)]
            local_start = max(0, start - base)
            local_end = max(0, end - base)
            if local_start >= len(dq) or local_end <= 0:
                return []
            local_end = min(local_end, len(dq))
            result = list(dq)[local_start:local_end]
            # Drop a contiguous prefix: only blocks at the head are evicted so absolute indices stay aligned
            # with the (still-growing) base counter.
            drop = local_end if local_start == 0 else 0
            for _ in range(drop):
                dq.popleft()
            self._base[(model, key)] = base + drop
            if drop:
                self._condition.notify_all()
            return result

    async def discard(self, model: str, key: uuid.UUID) -> None:
        async with self._condition:
            self._data.pop((model, key), None)
            self._base.pop((model, key), None)
            self._total.pop((model, key), None)
            self._condition.notify_all()

    def usage(self) -> dict[tuple[str, uuid.UUID], int] | None:
        return None


class CleanupTask:
    """Background eviction policy for :class:`StreamsRegistry`.

    Combines two complementary signals so long-running deployments stay bounded both in time and on disk:

    -   **TTL**: drop any buffer whose last append/finish is older than ``ttl`` seconds.
    -   **Disk usage**: when the aggregate backend usage exceeds ``disk_usage`` bytes, evict buffers in
        ``done-first then oldest-by-last_activity`` order until the total falls back under the threshold (or the
        registry runs out of candidates).

    Both signals are evaluated on every pass; the task tolerates a backend that returns ``None`` from
    :meth:`StreamsBackend.usage` (the disk-usage policy degrades to a no-op for that signal). At least one of
    ``ttl`` or ``disk_usage`` MUST be supplied — building a task with neither would have no effect.

    Lifecycle is bound to the owning :class:`StreamsRegistry`: :meth:`start` is called from
    :meth:`StreamsRegistry.aopen` and :meth:`stop` from :meth:`StreamsRegistry.aclose`. Both are idempotent.

    :param ttl: Idle time threshold in seconds, monotonic. ``None`` disables the TTL signal.
    :param disk_usage: Aggregate byte budget across the backend. ``None`` disables the disk-usage signal.
    :param period: Sleep interval between background passes (seconds).
    :raises ValueError: If both ``ttl`` and ``disk_usage`` are ``None`` or ``period`` is non-positive.
    """

    def __init__(self, *, ttl: float | None = None, disk_usage: int | None = None, period: float = 60.0) -> None:
        if ttl is None and disk_usage is None:
            raise ValueError("CleanupTask requires at least one of `ttl` or `disk_usage`")
        if period <= 0:
            raise ValueError("CleanupTask `period` must be positive")
        self.ttl = ttl
        self.disk_usage = disk_usage
        self.period = period
        self._task: asyncio.Task[None] | None = None
        self._registry: StreamsRegistry | None = None

    async def start(self, registry: "StreamsRegistry") -> None:
        """Schedule the background loop against *registry*. No-op if already running."""
        if self._task is not None:
            return
        self._registry = registry
        self._task = asyncio.create_task(self._run(), name="flama-streams-cleanup")

    async def stop(self) -> None:
        """Cancel the background loop and await its exit. No-op if not running."""
        if self._task is None:
            return
        task = self._task
        self._task = None
        self._registry = None
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def evict(self, registry: "StreamsRegistry") -> list[tuple[str, uuid.UUID]]:
        """Perform a single eviction pass against *registry* and return the number of buffers removed.

        Exposed primarily for tests and ad-hoc triggers; the background loop calls this on every tick.
        """
        return [
            *(await self._evict_by_ttl(registry, self.ttl) if self.ttl is not None else []),
            *(await self._evict_by_disk_usage(registry, self.disk_usage) if self.disk_usage is not None else []),
        ]

    async def _run(self) -> None:
        assert self._registry is not None
        registry = self._registry
        while True:
            try:
                await asyncio.sleep(self.period)
                await self.evict(registry)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Streams cleanup pass failed")

    @staticmethod
    async def _evict_by_ttl(registry: "StreamsRegistry", ttl: float) -> list[tuple[str, uuid.UUID]]:
        cutoff = time.monotonic() - ttl
        stale = [(model, key) for model, key, buffer in registry if buffer.timestamp < cutoff]
        for model, key in stale:
            await registry.remove(model, key)
        return stale

    @staticmethod
    async def _evict_by_disk_usage(registry: "StreamsRegistry", limit: int) -> list[tuple[str, uuid.UUID]]:
        if (usage := registry.backend.usage()) is None or (total := sum(usage.values())) <= limit:
            return []

        candidates = sorted(
            ((model, key, buffer) for (model, key, buffer) in registry if buffer.done),
            key=lambda item: item[2].timestamp,
        )
        evicted: list[tuple[str, uuid.UUID]] = []
        for model, key, _ in candidates:
            if total <= limit:
                break
            await registry.remove(model, key)
            total -= usage.get((model, key), 0)
            evicted.append((model, key))
        return evicted


@dataclasses.dataclass
class StreamBuffer:
    """Append-only generation buffer composed from an in-flight backend and an optional durable backend.

    A buffer is created by ``POST /stream/`` (or its OpenAI counterpart) — one per generation request. The
    background task drives a :class:`~flama.models.Event` stream (lifecycle markers and content
    interleaved as produced by :class:`~flama.models.LLMCodec`) into :meth:`append`, which signals
    :attr:`_condition` so any number of consumers can replay the current contents and then live-tail until
    :attr:`done` is set. The buffer itself is a pure recorder — it does not synthesize
    :class:`~flama.models.StartEvent` or :class:`~flama.models.StopEvent`; those flow in from the
    decoder (or are appended by the driver on error) like any other block.

    Storage is composed from two cooperating backends:

    -   :attr:`ephemeral`: an :class:`InMemoryStreamsBackend` (typically capacity-bounded) holding in-flight
        blocks. :meth:`read` pops from here first so capacity-bounded producers see backpressure as fast as
        the slowest consumer drains. Required; every buffer has one.
    -   :attr:`backend`: an optional durable backend (e.g. :class:`FileStreamsBackend`) holding every block
        for replay. ``None`` selects pure ephemeral mode (single-consumer protocols like OpenAI chat
        completions); set selects persistent mode (reconnectable streams like the native two-step flow).

    :meth:`append` writes to the durable backend first (when present) and then to ephemeral, so a producer
    suspended on full ephemeral capacity has already persisted that block — consumers reconnecting via
    :attr:`backend` see no gap. :meth:`read` pops from ephemeral and fills any holes from
    :attr:`backend`, which preserves single-source-of-truth semantics across reconnects.

    :param model: Per-model namespace this buffer lives under.
    :param id: Per-response identifier.
    :param ephemeral: In-flight backend (always set). Capacity bounds, if any, drive producer backpressure.
    :param backend: Optional durable backend used for replay reads and durable persistence.
    :param timestamp: Monotonic timestamp of the latest append; used by :class:`CleanupTask` to evict idle
        buffers.
    """

    model: str
    id: uuid.UUID
    ephemeral: StreamsBackend
    backend: StreamsBackend | None = None
    timestamp: float = dataclasses.field(default_factory=time.monotonic)
    _condition: asyncio.Condition = dataclasses.field(default_factory=asyncio.Condition, repr=False, compare=False)
    _output_tokens: int = dataclasses.field(default=0, repr=False, compare=False)
    _stop_reason: types.LLMTransportStopReason | None = dataclasses.field(default=None, repr=False, compare=False)

    @property
    def length(self) -> int:
        """Total number of events ever written (does not shrink on :meth:`read`-driven pops).

        Sourced from :attr:`backend` when present, otherwise from :attr:`ephemeral` (which reports cumulative
        appends, not resident size). Both backends agree on absolute indices.
        """
        source = self.backend if self.backend is not None else self.ephemeral
        return source.length().get((self.model, self.id), 0)

    @property
    def stop_reason(self) -> types.LLMTransportStopReason | None:
        """Final stop reason if a terminal :class:`StopEvent` has been appended; ``None`` otherwise."""
        return self._stop_reason

    @property
    def done(self) -> bool:
        """``True`` once a terminal :class:`StopEvent` has been observed."""
        return self._stop_reason is not None

    def __aiter__(self) -> t.AsyncIterator[Event]:
        """Return a fresh async iterator over every block from index ``0`` through completion.

        Each call instantiates an independent generator with its own local cursor, so multiple consumers
        can tail the same buffer without clobbering each other's positions. In pure-ephemeral mode (no
        :attr:`backend`) blocks are consumed once: subsequent iterators only see what hasn't been popped
        yet.
        """
        return self._iterate()

    async def _iterate(self) -> t.AsyncGenerator[Event, None]:
        """Replay persisted blocks, then live-tail under :attr:`_condition` until :attr:`done`."""
        for block in await self.read(0, self.length):
            yield block
        cursor = self.length
        done = self.done
        while not done:
            async with self._condition:
                while not self.done and cursor >= self.length:
                    await self._condition.wait()
                length = self.length
                done = self.done
            for block in await self.read(cursor, length):
                yield block
            cursor = length

    async def append(self, block: Event) -> None:
        """Persist *block* through both backends and notify waiters.

        Writes :attr:`backend` first (when present) so the durable record is updated before the producer can
        be suspended by a capacity-bounded :attr:`ephemeral`. Accumulates :attr:`TraceEvent.token_count`
        into :attr:`_output_tokens` so :meth:`error` can synthesise an accurate terminal
        :class:`StopEvent`, and captures :attr:`StopEvent.stop_reason` so :attr:`done` and
        :attr:`stop_reason` track without needing to peek into either backend.
        """
        if self.backend is not None:
            await self.backend.append(self.model, self.id, block)
        await self.ephemeral.append(self.model, self.id, block)
        async with self._condition:
            if isinstance(block, TraceEvent) and block.token_count is not None:
                self._output_tokens += block.token_count
            if isinstance(block, StopEvent):
                self._stop_reason = block.stop_reason
            self.timestamp = time.monotonic()
            self._condition.notify_all()

    async def error(self, reason: types.LLMTransportStopReason = "error") -> None:
        """Terminate the stream with a synthesised :class:`StopEvent`.

        Used by drivers when generation raises before the decoder's terminal :class:`StopEvent` is
        emitted. The output-token total is reconstructed from the :class:`TraceEvent` values observed
        during prior :meth:`append` calls.

        :param reason: ``stop_reason`` stamped on the synthesised :class:`StopEvent`.
        """
        await self.append(StopEvent(stop_reason=reason, output_tokens=self._output_tokens))

    async def load(self, stream: t.AsyncIterator[Event]) -> None:
        """Drain *stream* into the buffer, synthesising a terminal :class:`StopEvent` on failure.

        Used by serving layers as the producer side of the producer-consumer channel: the native flow
        mounts this on a :class:`~flama.background.BackgroundTask` so it runs after the POST body is
        flushed (while the GET tails the same buffer); single-step flows (OpenAI chat completions) drive
        it concurrently with body iteration via :func:`flama.concurrency.alongside`. The decoder owns the
        success-path :class:`~flama.models.StartEvent` / :class:`~flama.models.StopEvent`
        lifecycle, so this method just forwards every block it sees. If *stream* raises, the decoder
        never emits its terminal :class:`StopEvent`, so :meth:`error` is invoked to synthesise one;
        downstream consumers render that as a dialect-appropriate error frame.

        :class:`~flama.exceptions.FrameworkNotInstalled` is logged at ``error`` level (no traceback —
        it's a deployment issue, not a bug); every other exception goes through
        :meth:`logging.Logger.exception`.

        :param stream: Async iterator of blocks produced by :meth:`LLMModel.stream`.
        """
        try:
            async for block in stream:
                await self.append(block)
        except FrameworkNotInstalled as exc:
            logger.error("Stream backend missing dependency: %s", exc)
            await self.error()
        except Exception as exc:
            logger.exception("Stream generation failed: %s", exc)
            await self.error()

    async def read(self, start: int, end: int) -> list[Event]:
        """Read events in ``[start, end)`` from ephemeral first (with pop), filling holes from :attr:`backend`.

        Popping ephemeral on read realises producer backpressure: blocks linger in ephemeral until consumed,
        and a slow consumer suspends a capacity-bounded producer until it catches up. Blocks already popped
        by an earlier consumer are served from :attr:`backend` so reconnecting clients see no gap. In pure
        ephemeral mode (no :attr:`backend`) only the still-resident range is returned.

        :param start: Inclusive event index.
        :param end: Exclusive event index. Values past :attr:`length` are clamped.
        """
        length = self.length
        if start >= (end := min(end, length)) or start >= length:
            return []

        popped = await self.ephemeral.pop(self.model, self.id, start, end)
        if self.backend is None or len(popped) == end - start:
            return popped
        # Ephemeral served a contiguous *suffix* of ``[start, end)`` (or nothing). Fill the prefix from the
        # durable backend; absolute indices align across both stores by construction.
        prefix_end = end - len(popped)
        prefix = await self.backend.read(self.model, self.id, start, prefix_end) if start < prefix_end else []
        return [*prefix, *popped]


class ModelStreams:
    """All :class:`StreamBuffer` instances for a single model.

    Returned from :meth:`StreamsRegistry.add` and held by :class:`~flama.models.resources.llm.LLMResource`
    as :attr:`~flama.models.resources.llm.BaseLLMResource.streams`. Encapsulates the per-model namespace so
    resources can allocate, look up, and remove their own buffers without knowing the model name on every call
    or having access to other models' buffers.

    Holds two backends owned by the parent :class:`StreamsRegistry`:

    -   :attr:`_backend`: durable cold storage (e.g. :class:`FileStreamsBackend`). Used for buffers created
        with ``persist=True`` (the default) — typically native's two-step SSE flow with ``Last-Event-ID``
        reconnect, which requires replay.
    -   :attr:`_ephemeral_backend`: in-flight in-memory tier (typically
        :class:`InMemoryStreamsBackend(capacity=...)`). Used by every buffer for the live producer-consumer
        channel; for ``persist=False`` buffers it's the *only* storage (single-step protocols like OpenAI
        chat completions).

    :param name: Per-model namespace this handle lives under.
    :param backend: Durable cold-storage backend.
    :param ephemeral_backend: In-flight in-memory backend.
    """

    def __init__(self, name: str, backend: StreamsBackend, ephemeral_backend: StreamsBackend) -> None:
        self.name = name
        self._backend = backend
        self._ephemeral_backend = ephemeral_backend
        self._buffers: dict[uuid.UUID, StreamBuffer] = {}

    def __contains__(self, key: uuid.UUID, /) -> bool:
        return key in self._buffers

    def __getitem__(self, key: uuid.UUID, /) -> StreamBuffer:
        return self._buffers[key]

    def __iter__(self) -> t.Iterator[tuple[uuid.UUID, StreamBuffer]]:
        """Yield ``(key, buffer)`` pairs. Snapshotted for safe iteration under concurrent mutation."""
        return iter(list(self._buffers.items()))

    def __len__(self) -> int:
        return len(self._buffers)

    async def create(self, *, persist: bool = True) -> tuple[uuid.UUID, StreamBuffer]:
        """Allocate a fresh empty :class:`StreamBuffer` under this model.

        Lifecycle markers (:class:`~flama.models.StartEvent`, :class:`~flama.models.StopEvent`) are
        synthesised by the producing :class:`~flama.models.LLMCodec` and flow into the buffer via
        :meth:`StreamBuffer.append` like any other block.

        :param persist: When ``True`` (default) the buffer is wired with both the durable backend and the
            in-flight ephemeral backend, so reconnecting clients can replay from cold storage. When ``False``
            the durable backend is omitted; the ephemeral backend is the only storage and the protocol must
            be single-consumer (OpenAI chat completions).
        :return: A ``(uuid, buffer)`` tuple. The caller stores the uuid and is responsible for advertising it
            to clients.
        """
        buffer_id = uuid.uuid4()
        buffer = StreamBuffer(
            model=self.name,
            id=buffer_id,
            ephemeral=self._ephemeral_backend,
            backend=self._backend if persist else None,
        )
        self._buffers[buffer_id] = buffer
        return buffer_id, buffer

    async def remove(self, key: uuid.UUID) -> StreamBuffer | None:
        """Detach *key* from this model's pool, drop its log from every backend, and return the buffer.

        Always discards from both :attr:`_ephemeral_backend` and :attr:`_backend` so capacity-bounded
        ephemeral entries free their slot (waking any suspended producer) regardless of which mode the
        buffer was created in.

        :param key: Per-response identifier.
        :return: A :class:`StreamBuffer` if found, otherwise ``None``.
        """
        buffer = self._buffers.pop(key, None)
        if buffer is not None:
            await self._ephemeral_backend.discard(self.name, key)
            await self._backend.discard(self.name, key)
        return buffer


class StreamsRegistry:
    """In-memory front for stream buffers, partitioned by model name.

    Owns one :class:`ModelStreams` per registered model and the two registry-wide backends; delegates durable
    persistence to :attr:`backend`, in-flight in-memory storage to :attr:`ephemeral_backend`, and (optionally)
    background eviction to a :class:`CleanupTask`. The lifecycle methods (:meth:`aopen`, :meth:`aclose`)
    forward to both backends and are idempotent so module wiring can call them under varying lifecycle
    conditions.

    Resources do not interact with the registry directly: they receive a :class:`ModelStreams` via
    :meth:`add` and operate on it. The registry is the unit of cross-model coordination — iteration
    (used by :class:`CleanupTask`) yields ``(model, key, buffer)`` triples across every registered model, and
    :meth:`remove` is the cross-model eviction entry point.

    :param backend: Durable cold-storage backend. Defaults to a fresh :class:`FileStreamsBackend`.
    :param ephemeral_backend: In-flight in-memory backend used by every buffer and as the *only* storage for
        ``persist=False`` buffers. Defaults to a fresh :class:`InMemoryStreamsBackend(capacity=...)` bounded
        at :data:`DEFAULT_EPHEMERAL_CAPACITY` so capacity-driven backpressure is on by default for
        persistent buffers; pass an unbounded :class:`InMemoryStreamsBackend()` to disable it.
    :param cleanup: Optional :class:`CleanupTask` driving background eviction. ``None`` disables the
        background sweep (callers may still call :meth:`cleanup` manually).
    """

    def __init__(
        self,
        *,
        backend: StreamsBackend | None = None,
        ephemeral_backend: StreamsBackend | None = None,
        cleanup: CleanupTask | None = None,
    ) -> None:
        self.backend: StreamsBackend = backend if backend is not None else FileStreamsBackend()
        self.ephemeral_backend: StreamsBackend = (
            ephemeral_backend
            if ephemeral_backend is not None
            else InMemoryStreamsBackend(capacity=DEFAULT_EPHEMERAL_CAPACITY)
        )
        self.cleanup_task = cleanup
        self._streams: dict[str, ModelStreams] = {}

    def __contains__(self, name: str, /) -> bool:
        return name in self._streams

    def __getitem__(self, name: str, /) -> ModelStreams:
        return self._streams[name]

    def __len__(self) -> int:
        return sum(len(model) for model in self._streams.values())

    def __iter__(self) -> t.Iterator[tuple[str, uuid.UUID, StreamBuffer]]:
        """Yield ``(model, key, buffer)`` triples across every registered model. Snapshotted for safe iteration
        while concurrent mutators (e.g. :meth:`remove`) may run.
        """
        return iter([(model.name, key, buffer) for model in self._streams.values() for key, buffer in model])

    def add(self, name: str) -> ModelStreams:
        """Register *name* and return its :class:`ModelStreams` handle. Idempotent.

        Called by :class:`~flama.models.modules.ModelsModule` when wiring an LLM resource. Subsequent calls with
        the same *name* return the same handle so re-wiring (decorator-mounted resources, test setup) does not
        clobber already-allocated buffers.

        :param name: Per-model namespace.
        :return: The per-model handle (existing or freshly allocated).
        """
        return self._streams.setdefault(
            name,
            ModelStreams(name, self.backend, self.ephemeral_backend),
        )

    async def aopen(self) -> None:
        """Open both backends and start the cleanup task (if any). Idempotent."""
        await self.backend.aopen()
        await self.ephemeral_backend.aopen()
        if self.cleanup_task is not None:
            await self.cleanup_task.start(self)

    async def aclose(self) -> None:
        """Stop the cleanup task and close both backends. Idempotent."""
        if self.cleanup_task is not None:
            await self.cleanup_task.stop()
        self._streams.clear()
        await self.ephemeral_backend.aclose()
        await self.backend.aclose()

    async def __aenter__(self) -> "StreamsRegistry":
        await self.aopen()
        return self

    async def __aexit__(self, *_: t.Any) -> None:
        await self.aclose()

    async def remove(self, model: str, key: uuid.UUID) -> StreamBuffer | None:
        """Cross-model eviction entry point: drop ``(model, key)`` from the registry.

        Used by :class:`CleanupTask` to evict stale buffers across every model. Resources don't call this — they
        use :meth:`ModelStreams.remove` on their own handle. Returns ``None`` if *model* is unknown.

        :param model: Per-model namespace.
        :param key: Per-response identifier.
        :return: The evicted :class:`StreamBuffer`, or ``None`` if no such ``(model, key)``.
        """
        if (model_streams := self._streams.get(model)) is None:
            return None
        return await model_streams.remove(key)
