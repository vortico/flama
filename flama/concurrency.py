import asyncio
import concurrent.futures
import contextlib
import contextvars
import functools
import inspect
import multiprocessing
import os
import sys
import threading
import typing as t

__all__ = [
    "FileReader",
    "iterate",
    "is_async",
    "run",
    "run_in_executor",
    "run_task_group",
    "AsyncProcess",
    "with_heartbeat",
    "alongside",
]

R = t.TypeVar("R", covariant=True)
T = t.TypeVar("T")
P = t.ParamSpec("P")


class FileReader:
    """Async iterator that streams file content in chunks via a background producer task.

    A bounded :class:`asyncio.Queue` bridges the producer (reading via :func:`asyncio.to_thread`)
    with the async consumer, allowing disk reads to overlap with ASGI sends.  While the consumer
    is forwarding chunk *N* to the client, the producer can already be reading chunk *N+1*.

    A ``None`` sentinel signals end-of-stream.  Call :meth:`aclose` to cancel the producer early;
    ``async for`` does **not** call it automatically on plain async iterators, so callers must
    wrap usage in ``try/finally``.

    :param path: File path to read.
    :param chunk_size: Maximum bytes per chunk.
    :param start: Byte offset to start reading from.
    :param end: Byte offset to stop reading at (exclusive). ``None`` reads to EOF.
    """

    def __init__(
        self, path: "str | os.PathLike[str]", chunk_size: int, start: int | None = None, end: int | None = None
    ) -> None:
        self._path = path
        self._chunk_size = chunk_size
        self._start = start if start is not None else 0
        self._end = end
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=1)
        self._task: asyncio.Task[None] | None = None

    async def _reader(self) -> None:
        f = t.cast(t.BinaryIO, await asyncio.to_thread(open, self._path, "rb"))
        try:
            if self._start:
                await asyncio.to_thread(f.seek, self._start)
            remaining = self._end - self._start if self._end is not None else None
            while True:
                read_size = min(self._chunk_size, remaining) if remaining is not None else self._chunk_size
                chunk = await asyncio.to_thread(f.read, read_size)
                if not chunk:
                    break
                await self._queue.put(chunk)
                if remaining is not None:
                    remaining -= len(chunk)
                    if remaining <= 0:
                        break
        finally:
            await asyncio.to_thread(f.close)
            await self._queue.put(None)

    def __aiter__(self) -> "FileReader":
        self._task = asyncio.create_task(self._reader())
        return self

    async def __anext__(self) -> bytes:
        if (chunk := await self._queue.get()) is None:
            raise StopAsyncIteration

        return chunk

    async def aclose(self) -> None:
        """Cancel the producer task and drain the queue.

        Safe to call multiple times or after iteration has already completed.
        """
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                while True:
                    self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def __aenter__(self) -> "FileReader":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()


def _close_quietly(obj: t.Any) -> None:
    """Call ``obj.close()`` if it exists, suppressing every exception.

    Used by :func:`iterate` to drop generator / file-like resources on cleanup; see that
    function's docstring for the contract.
    """
    close = getattr(obj, "close", None)
    if callable(close):
        with contextlib.suppress(BaseException):
            close()


async def iterate(
    iterator: t.Iterable[T] | t.AsyncIterable[T],
    *,
    executor: concurrent.futures.Executor | None = None,
) -> t.AsyncGenerator[T, None]:
    """Normalise any iterable into an async iterator.

    If *iterator* is already an :class:`~collections.abc.AsyncIterable` it is yielded from
    directly. Otherwise the synchronous iterable is consumed in a background thread on
    *executor* (``None`` selects the default thread pool) and items are passed through a
    bounded :class:`asyncio.Queue` for natural backpressure.

    Pass an explicit *executor* when the source carries thread affinity (e.g. CUDA / Metal
    streams) and must run on a specific worker.

    The source's ``close()``, if any, is called from the producer thread when iteration ends —
    whether the consumer reaches StopIteration, cancels the task, ``aclose()``\\ s the
    generator, or raises out of the loop. This matches generator semantics and lets backends
    release resources (KV caches, file handles, …) promptly without waiting for GC. Iterables
    without a ``close`` are left untouched.

    :param iterator: Synchronous or asynchronous iterable to wrap.
    :param executor: Executor for the sync-source producer thread; ``None`` uses the default pool.
    :return: Async iterator yielding the same values.
    """
    if isinstance(iterator, t.AsyncIterable):
        async for item in iterator:
            yield t.cast(T, item)
        return

    queue: asyncio.Queue[T] = asyncio.Queue(maxsize=1)
    loop = asyncio.get_running_loop()
    cancelled = threading.Event()
    # Holds the in-flight ``queue.put`` future so consumer cleanup can cancel it and unblock
    # the producer thread when the consumer goes away (otherwise a maxsize=1 queue with no
    # reader would pin the producer forever).
    pending: list[concurrent.futures.Future[t.Any]] = []

    def _produce() -> None:
        try:
            for item in iterator:
                if cancelled.is_set():
                    return
                fut = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
                pending.append(fut)
                try:
                    fut.result()
                except concurrent.futures.CancelledError:
                    return
                finally:
                    pending.remove(fut)
        finally:
            _close_quietly(iterator)
            # Wake the consumer (if still around) so its ``queue.get`` returns; if the consumer
            # already cancelled and drained, this still completes against the empty queue.
            sentinel = asyncio.run_coroutine_threadsafe(queue.put(t.cast(T, StopIteration)), loop)
            with contextlib.suppress(BaseException):
                sentinel.result()

    future = loop.run_in_executor(executor, _produce)

    try:
        while (item := await queue.get()) is not StopIteration:
            yield item
    finally:
        cancelled.set()
        for fut in list(pending):
            fut.cancel()
        # Drain any items the producer pushed before noticing cancellation so its sentinel
        # ``queue.put`` finds an empty slot and the producer thread can exit cleanly.
        with contextlib.suppress(asyncio.QueueEmpty):
            while True:
                queue.get_nowait()
        with contextlib.suppress(BaseException):
            await future


def is_async(obj: t.Any) -> t.TypeGuard[t.Callable[..., t.Coroutine]]:
    """Check if given object is an async function, callable or partialised function.

    :param obj: Object to check.
    :return: True if it's an async function, callable or partialised function.
    """
    while isinstance(obj, functools.partial):
        obj = obj.func

    return inspect.iscoroutinefunction(obj) or inspect.iscoroutinefunction(getattr(obj, "__call__", None))


async def run(
    func: t.Callable[P, R] | t.Callable[P, t.Awaitable[R]],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """Run *func* on the default thread pool, awaiting its result.

    Thin shortcut for :func:`run_in_executor` with ``executor=None``: async callables are
    awaited inline and sync callables run on the default thread pool with the caller's
    :class:`~contextvars.Context` propagated. Use :func:`run_in_executor` directly when the
    work has thread affinity (e.g. CUDA / Metal streams) or needs an isolated pool.

    :param func: Function to run.
    :param args: Positional arguments.
    :param kwargs: Keyword arguments.
    :return: Function returned value.
    """
    return await run_in_executor(None, func, *args, **kwargs)


async def run_in_executor(
    executor: concurrent.futures.Executor | None,
    func: t.Callable[P, R] | t.Callable[P, t.Awaitable[R]],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """Run *func* on *executor*, awaiting its result.

    Async callables are awaited directly (the executor argument becomes a no-op). Sync
    callables are submitted to *executor* with the caller's :class:`~contextvars.Context`
    copied into the worker thread, mirroring :func:`asyncio.to_thread`'s context propagation
    for the default-pool case. Pass ``executor=None`` to use the loop's default pool — same
    behaviour as :func:`run`.

    :param executor: Executor to run *func* on, or ``None`` to use the default thread pool.
    :param func: Function to run.
    :param args: Positional arguments.
    :param kwargs: Keyword arguments.
    :return: Function returned value.
    """
    if is_async(func):
        return await func(*args, **kwargs)

    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    call = functools.partial(ctx.run, func, *args, **kwargs)
    return t.cast(R, await loop.run_in_executor(executor, call))


if sys.version_info >= (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover

    async def run_task_group(*tasks: t.Coroutine[t.Any, t.Any, t.Any]) -> list[asyncio.Task]:
        """Run a group of tasks.

        :param tasks: Tasks to run.
        :result: Finished tasks.
        """
        async with asyncio.TaskGroup() as task_group:
            return [task_group.create_task(task) for task in tasks]

else:  # pragma: no cover

    async def run_task_group(*tasks: t.Coroutine[t.Any, t.Any, t.Any]) -> list[asyncio.Task]:
        """Run a group of tasks.

        :param tasks: Tasks to run.
        :result: Finished tasks.
        """
        tasks_list = [asyncio.create_task(task) for task in tasks]
        await asyncio.wait(tasks_list)
        return tasks_list


async def with_heartbeat(
    source: t.AsyncIterator[T], *, interval: float, heartbeat: t.Callable[[], T]
) -> t.AsyncIterator[T]:
    """Yield from *source* while injecting periodic *heartbeat* values during idle periods.

    Races each ``__anext__`` against an :class:`asyncio.sleep` of *interval* seconds. When the
    timer wins (no upstream item in time), a heartbeat is yielded; the next iteration resumes
    waiting on the (still-pending) upstream task so no upstream item is lost or duplicated.
    Useful for keeping idle long-poll / SSE connections alive through network proxies that
    enforce read timeouts.

    :param source: Async source whose items are forwarded transparently.
    :param interval: Idle threshold in seconds before injecting a heartbeat. Must be positive.
    :param heartbeat: Zero-arg callable producing the heartbeat value to yield.
    """
    if interval <= 0:
        raise ValueError("interval must be positive")
    iterator = source.__aiter__()

    async def _next() -> T:
        return await iterator.__anext__()

    pending: asyncio.Task[T] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.create_task(_next())
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if pending in done:
                try:
                    yield pending.result()
                except StopAsyncIteration:
                    return
                pending = None
            else:
                yield heartbeat()
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            try:
                await pending
            except (asyncio.CancelledError, StopAsyncIteration, Exception):
                pass


async def alongside(
    source: t.AsyncIterator[T],
    coroutine: t.Callable[[], t.Coroutine[t.Any, t.Any, t.Any]],
) -> t.AsyncIterator[T]:
    """Yield from *source* while a *coroutine* runs concurrently on the event loop.

    Schedules ``coroutine()`` as an :class:`asyncio.Task` before consuming *source*, then forwards
    every item the source yields. When iteration ends — normally, by ``break``, or because the
    consumer closes the generator (e.g. client disconnect on an SSE response) — the concurrent task
    is cancelled and awaited so it never outlives the iterator. Exceptions from the concurrent task
    are suppressed: the source's normal completion or failure remains the visible outcome; the
    concurrent task is expected to handle its own errors out-of-band (write them to a buffer,
    log them, etc.).
    Use for "producer running alongside its consumer" patterns where the framework's
    :class:`~flama.background.BackgroundTask` (which fires *after* the response body) would
    deadlock the consumer.

    :param source: Iterator whose items are forwarded transparently.
    :param coroutine: Zero-arg callable returning the coroutine to run concurrently with iteration.
    """
    producer = asyncio.create_task(coroutine())
    try:
        async for item in source:
            yield item
    finally:
        if not producer.done():
            producer.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await producer


class AsyncProcess(multiprocessing.Process):
    """Multiprocessing Process class whose target is an async function."""

    _target: t.Callable[..., t.Any | t.Coroutine] | None
    _args: list[t.Any]
    _kwargs: dict[str, t.Any]

    def run(self) -> None:
        if self._target:
            result_or_task = self._target(*self._args, **self._kwargs)

            asyncio.run(result_or_task) if is_async(self._target) else result_or_task
