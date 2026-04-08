import asyncio
import functools
import inspect
import multiprocessing
import os
import sys
import typing as t

__all__ = ["FileReader", "iterate_in_threadpool", "is_async", "run", "run_task_group", "AsyncProcess"]

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


async def iterate_in_threadpool(iterator: t.Iterable[T]) -> t.AsyncIterator[T]:
    """Wrap a synchronous iterable into an async iterator using a producer thread and an async queue.

    The sync iterator is consumed in a background thread. Items are passed to the async side through
    a bounded :class:`asyncio.Queue`, providing natural backpressure.

    :param iterator: Synchronous iterable to wrap.
    :return: Async iterator yielding the same values.
    """
    queue: asyncio.Queue[T] = asyncio.Queue(maxsize=1)
    loop = asyncio.get_running_loop()

    def _produce() -> None:
        try:
            for item in iterator:
                asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(t.cast(T, StopIteration)), loop).result()

    future = loop.run_in_executor(None, _produce)

    while (item := await queue.get()) is not StopIteration:
        yield item

    await future


def is_async(obj: t.Any) -> t.TypeGuard[t.Callable[..., t.Awaitable[t.Any]]]:
    """Check if given object is an async function, callable or partialised function.

    :param obj: Object to check.
    :return: True if it's an async function, callable or partialised function.
    """
    while isinstance(obj, functools.partial):
        obj = obj.func

    return inspect.iscoroutinefunction(obj) or inspect.iscoroutinefunction(getattr(obj, "__call__"))


async def run(
    func: t.Callable[P, R] | t.Callable[P, t.Awaitable[R]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """Run a function either as asyncio awaiting it if it's an async function or running it in a thread if it's a
    sync function.

    :param func: Function to run.
    :param args: Positional arguments.
    :param kwargs: Keyword arguments.
    :return: Function returned value.
    """
    if is_async(func):
        return await func(*args, **kwargs)

    return t.cast(R, await asyncio.to_thread(func, *args, **kwargs))


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


class AsyncProcess(multiprocessing.Process):
    """Multiprocessing Process class whose target is an async function."""

    _target: t.Callable[..., t.Any | t.Coroutine] | None
    _args: list[t.Any]
    _kwargs: dict[str, t.Any]

    def run(self) -> None:
        if self._target:
            result_or_task = self._target(*self._args, **self._kwargs)

            asyncio.run(result_or_task) if is_async(self._target) else result_or_task
