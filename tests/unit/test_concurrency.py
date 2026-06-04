import asyncio
import concurrent.futures
import contextvars
import functools
import pathlib
import threading
import typing as t

import pytest

from flama import concurrency


class TestCaseFileReader:
    """Cover :class:`concurrency.FileReader` lifecycle, range reads and early-close drain."""

    @pytest.fixture(scope="function")
    def file_path(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "payload.bin"
        path.write_bytes(b"abcdefghijklmnopqrstuvwxyz")
        return path

    @pytest.mark.parametrize(
        ["chunk_size", "start", "end", "expected"],
        [
            pytest.param(8, None, None, [b"abcdefgh", b"ijklmnop", b"qrstuvwx", b"yz"], id="full_file_multi_chunk"),
            pytest.param(64, None, None, [b"abcdefghijklmnopqrstuvwxyz"], id="full_file_single_chunk"),
            pytest.param(4, 2, 12, [b"cdef", b"ghij", b"kl"], id="range_multi_chunk"),
            pytest.param(4, 2, 4, [b"cd"], id="range_single_chunk"),
            pytest.param(8, 24, None, [b"yz"], id="from_offset_to_eof"),
        ],
    )
    async def test_iteration(
        self,
        file_path: pathlib.Path,
        chunk_size: int,
        start: int | None,
        end: int | None,
        expected: list[bytes],
    ) -> None:
        reader = concurrency.FileReader(file_path, chunk_size=chunk_size, start=start, end=end)

        async with reader as it:
            collected = [chunk async for chunk in it]

        assert collected == expected

    async def test_aclose_cancels_producer_and_drains_queue(self, file_path: pathlib.Path) -> None:
        reader = concurrency.FileReader(file_path, chunk_size=2)

        it = reader.__aiter__()
        first = await it.__anext__()
        assert first == b"ab"
        await asyncio.sleep(0)

        await reader.aclose()

        assert reader._task is not None
        assert reader._task.done()

    async def test_aclose_is_idempotent_when_task_done(self, file_path: pathlib.Path) -> None:
        reader = concurrency.FileReader(file_path, chunk_size=64)
        async for _ in reader:
            pass

        await reader.aclose()
        await reader.aclose()

    async def test_aclose_safe_before_iteration(self, file_path: pathlib.Path) -> None:
        reader = concurrency.FileReader(file_path, chunk_size=8)

        await reader.aclose()


class TestCaseIterate:
    """Cover :func:`concurrency.iterate` normalising sync and async sources."""

    @pytest.mark.parametrize(
        ["source_factory", "expected"],
        [
            pytest.param(lambda: iter([1, 2, 3]), [1, 2, 3], id="sync_iterable"),
            pytest.param(lambda: (v for v in (1, 2, 3)), [1, 2, 3], id="sync_generator"),
            pytest.param(lambda: [], [], id="sync_empty"),
        ],
    )
    async def test_sync_source(self, source_factory: t.Callable[[], t.Iterable[int]], expected: list[int]) -> None:
        out = [item async for item in concurrency.iterate(source_factory())]

        assert out == expected

    async def test_async_source_passes_through(self) -> None:
        async def _src() -> t.AsyncIterator[int]:
            for v in (1, 2, 3):
                yield v

        out = [item async for item in concurrency.iterate(_src())]

        assert out == [1, 2, 3]


class TestCaseIsAsync:
    """Cover :func:`concurrency.is_async` across plain callables, coroutines and partials."""

    @pytest.mark.parametrize(
        ["obj", "expected"],
        [
            pytest.param(lambda: None, False, id="sync_lambda"),
            pytest.param(int, False, id="sync_callable"),
            pytest.param(_async_noop := (lambda: None), False, id="sync_function"),
            pytest.param(functools.partial(lambda x: x, 1), False, id="sync_partial"),
        ],
    )
    def test_sync_returns_false(self, obj: t.Any, expected: bool) -> None:
        assert concurrency.is_async(obj) is expected

    async def test_async_function(self) -> None:
        async def _f() -> None: ...

        assert concurrency.is_async(_f) is True

    async def test_async_partial(self) -> None:
        async def _f(x: int) -> int:
            return x

        assert concurrency.is_async(functools.partial(_f, 1)) is True

    async def test_async_callable(self) -> None:
        class _Callable:
            async def __call__(self) -> None: ...

        assert concurrency.is_async(_Callable()) is True


class TestCaseRun:
    """Cover :func:`concurrency.run` dispatch on sync vs async targets."""

    async def test_async_target(self) -> None:
        async def _f(x: int) -> int:
            return x + 1

        assert await concurrency.run(_f, 1) == 2

    async def test_sync_target(self) -> None:
        def _f(x: int) -> int:
            return x * 2

        assert await concurrency.run(_f, 3) == 6


class TestCaseRunInExecutor:
    """Cover :func:`concurrency.run_in_executor` — explicit executor pinning + contextvars."""

    async def test_routes_sync_to_supplied_executor(self) -> None:
        """The sync callable runs on a thread owned by the supplied executor, not the default pool."""
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="run-in-executor-test")

        def _f() -> int:
            return threading.get_ident()

        try:
            ident = await concurrency.run_in_executor(executor, _f)
            expected = await asyncio.wrap_future(executor.submit(threading.get_ident))
            assert ident == expected
        finally:
            executor.shutdown(wait=True)

    async def test_executor_none_uses_default_pool(self) -> None:
        """``executor=None`` matches :func:`run`'s behaviour by routing to the loop's default pool."""

        def _f(x: int, *, y: int) -> int:
            return x + y

        assert await concurrency.run_in_executor(None, _f, 2, y=3) == 5

    async def test_async_target_bypasses_executor(self) -> None:
        """Async callables are awaited inline; the executor is ignored even if supplied."""
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        async def _f(x: int) -> int:
            return x + 10

        try:
            assert await concurrency.run_in_executor(executor, _f, 5) == 15
        finally:
            executor.shutdown(wait=True)

    async def test_propagates_contextvars_to_worker(self) -> None:
        """The caller's :class:`~contextvars.Context` is copied into the executor thread, mirroring
        :func:`asyncio.to_thread`'s implicit contextvars hand-off so request-scope values
        (dependency-injection state, OpenTelemetry contexts, ...) survive the thread hop."""
        var: contextvars.ContextVar[str] = contextvars.ContextVar("test-var")
        var.set("from-caller")
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        try:
            assert await concurrency.run_in_executor(executor, var.get) == "from-caller"
        finally:
            executor.shutdown(wait=True)

    async def test_propagates_exception_from_worker(self) -> None:
        """Worker-raised exceptions surface at the await site untouched."""
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        def _f() -> None:
            raise RuntimeError("boom")

        try:
            with pytest.raises(RuntimeError, match="boom"):
                await concurrency.run_in_executor(executor, _f)
        finally:
            executor.shutdown(wait=True)


class TestCaseIterateExecutor:
    """Cover :func:`concurrency.iterate` executor pinning and source-close cleanup."""

    async def test_producer_runs_on_supplied_executor(self) -> None:
        """The synchronous producer runs on a thread owned by the supplied executor, mirroring
        the affinity contract that :class:`~flama.models.engine.backend.llm.mlx.MLXBackend` relies on."""
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="iterate-test")
        idents: list[int] = []

        def _src() -> t.Iterator[int]:
            for v in (1, 2, 3):
                idents.append(threading.get_ident())
                yield v

        try:
            out = [item async for item in concurrency.iterate(_src(), executor=executor)]
            expected = await asyncio.wrap_future(executor.submit(threading.get_ident))
            assert out == [1, 2, 3]
            assert idents and all(ident == expected for ident in idents)
        finally:
            executor.shutdown(wait=True)

    async def test_closes_source_on_normal_completion(self) -> None:
        """When the consumer drains every item, the producer thread still calls ``source.close()`` —
        generators get a clean shutdown rather than waiting on GC for the finalizer to fire."""

        class _Tracking:
            def __init__(self) -> None:
                self.closed = threading.Event()

            def __iter__(self) -> "_Tracking":
                self._chunks = iter((1, 2))
                return self

            def __next__(self) -> int:
                return next(self._chunks)

            def close(self) -> None:
                self.closed.set()

        source = _Tracking()
        out = [item async for item in concurrency.iterate(source)]

        assert out == [1, 2]
        # The producer thread runs ``close()`` from its ``finally`` after the sentinel push has
        # been scheduled; awaiting the loop briefly lets that finalisation thread observe the event.
        await asyncio.to_thread(source.closed.wait, 5.0)
        assert source.closed.is_set()

    async def test_closes_source_on_aclose(self) -> None:
        """``aclose`` mid-iteration cancels the in-flight ``queue.put``, lets the producer return,
        and runs ``source.close()`` on the producer thread — preventing the bounded queue from
        pinning the producer when the consumer disappears."""

        class _Tracking:
            def __init__(self) -> None:
                self.closed = threading.Event()
                self._chunks = iter(range(100))

            def __iter__(self) -> "_Tracking":
                return self

            def __next__(self) -> int:
                return next(self._chunks)

            def close(self) -> None:
                self.closed.set()

        source = _Tracking()
        agen = concurrency.iterate(source)

        first = await anext(agen)
        await agen.aclose()

        assert first == 0
        await asyncio.to_thread(source.closed.wait, 5.0)
        assert source.closed.is_set()

    async def test_close_skipped_for_iterables_without_close(self) -> None:
        """Plain iterables (lists, tuples, ...) have no ``close`` method; iteration must finish
        cleanly without raising :class:`AttributeError` from the producer thread."""
        out = [item async for item in concurrency.iterate([1, 2, 3])]

        assert out == [1, 2, 3]


class TestCaseWithHeartbeat:
    """Cover :func:`concurrency.with_heartbeat` — periodic heartbeat injection during idle source."""

    async def test_yields_source_items(self) -> None:
        async def _src() -> t.AsyncIterator[int]:
            for v in (1, 2, 3):
                yield v

        out = [v async for v in concurrency.with_heartbeat(_src(), interval=10.0, heartbeat=lambda: -1)]

        assert out == [1, 2, 3]

    async def test_emits_heartbeat_on_idle(self) -> None:
        async def _src() -> t.AsyncIterator[int]:
            await asyncio.sleep(0.05)
            yield 1

        ticks: list[int] = []
        async for v in concurrency.with_heartbeat(_src(), interval=0.01, heartbeat=lambda: -1):
            ticks.append(v)
            if v == 1:
                break

        assert ticks[-1] == 1
        assert ticks[:-1].count(-1) >= 1

    async def test_no_loss_after_heartbeat(self) -> None:
        async def _src() -> t.AsyncIterator[str]:
            await asyncio.sleep(0.03)
            yield "a"
            yield "b"

        observed = [v async for v in concurrency.with_heartbeat(_src(), interval=0.01, heartbeat=lambda: "-")]

        assert "a" in observed and "b" in observed
        assert observed[-2:] == ["a", "b"]

    async def test_pending_task_cancelled_on_consumer_break(self) -> None:
        """The ``finally`` block cancels and awaits the pending upstream task when iteration exits early."""
        upstream_cancelled = asyncio.Event()

        async def _src() -> t.AsyncIterator[int]:
            try:
                await asyncio.sleep(10.0)
                yield 1  # pragma: no cover
            except asyncio.CancelledError:
                upstream_cancelled.set()
                raise

        ticks: list[int] = []
        async for v in concurrency.with_heartbeat(_src(), interval=0.01, heartbeat=lambda: -1):
            ticks.append(v)
            if len(ticks) >= 1:
                break

        await asyncio.wait_for(upstream_cancelled.wait(), timeout=1.0)

    @pytest.mark.parametrize(
        ["interval", "exception"],
        [
            pytest.param(0, ValueError("positive"), id="zero"),
            pytest.param(-1.0, ValueError("positive"), id="negative"),
        ],
        indirect=["exception"],
    )
    async def test_invalid_interval(self, interval: float, exception) -> None:
        async def _src() -> t.AsyncIterator[int]:
            yield 1  # pragma: no cover

        with exception:
            async for _ in concurrency.with_heartbeat(_src(), interval=interval, heartbeat=lambda: 0):
                pass  # pragma: no cover


class TestCaseAlongside:
    """Cover :func:`concurrency.alongside` — yield from a source while a coroutine runs concurrently."""

    async def test_yields_every_source_item(self) -> None:
        async def _producer() -> None:
            await asyncio.sleep(0)

        async def _src() -> t.AsyncIterator[int]:
            for v in (1, 2, 3):
                yield v

        out = [v async for v in concurrency.alongside(_src(), _producer)]

        assert out == [1, 2, 3]

    async def test_producer_starts_before_first_item_is_consumed(self) -> None:
        producer_started = asyncio.Event()

        async def _producer() -> None:
            producer_started.set()

        async def _src() -> t.AsyncIterator[int]:
            await asyncio.wait_for(producer_started.wait(), timeout=1.0)
            yield 1

        out = [v async for v in concurrency.alongside(_src(), _producer)]

        assert out == [1]

    async def test_producer_finishes_when_source_outlives_it(self) -> None:
        producer_done = asyncio.Event()

        async def _producer() -> None:
            await asyncio.sleep(0)
            producer_done.set()

        async def _src() -> t.AsyncIterator[int]:
            yield 1
            await producer_done.wait()
            yield 2

        out = [v async for v in concurrency.alongside(_src(), _producer)]

        assert out == [1, 2]
        assert producer_done.is_set()

    async def test_producer_cancelled_when_iteration_exits_early(self) -> None:
        cancelled = asyncio.Event()

        async def _producer() -> None:
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        async def _src() -> t.AsyncIterator[int]:
            yield 1
            yield 2  # pragma: no cover

        async for v in concurrency.alongside(_src(), _producer):
            if v == 1:
                break

        await asyncio.wait_for(cancelled.wait(), timeout=1.0)

    async def test_producer_exception_is_suppressed(self) -> None:
        async def _producer() -> None:
            raise RuntimeError("boom")

        async def _src() -> t.AsyncIterator[int]:
            yield 1
            yield 2

        out = [v async for v in concurrency.alongside(_src(), _producer)]

        assert out == [1, 2]


async def _async_process_target_async(path: str) -> None:
    """Module-level async target so :class:`multiprocessing.Process` can pickle it on macOS spawn."""
    await asyncio.sleep(0)
    pathlib.Path(path).write_text("async")


def _async_process_target_sync(path: str) -> None:
    """Module-level sync target for :class:`AsyncProcess` to exercise the non-coroutine branch."""
    pathlib.Path(path).write_text("sync")


class TestCaseAsyncProcess:
    """Cover :class:`concurrency.AsyncProcess` running async and sync targets."""

    @pytest.mark.parametrize(
        ["target", "expected"],
        [
            pytest.param(_async_process_target_async, "async", id="async_target"),
            pytest.param(_async_process_target_sync, "sync", id="sync_target"),
        ],
    )
    def test_run(self, tmp_path: pathlib.Path, target: t.Callable[..., t.Any], expected: str) -> None:
        marker = tmp_path / "marker.txt"
        process = concurrency.AsyncProcess(target=target, args=(str(marker),))
        process.start()
        process.join(timeout=10.0)

        assert process.exitcode == 0
        assert marker.read_text() == expected

    def test_run_without_target_is_noop(self) -> None:
        """An :class:`AsyncProcess` instantiated without a target should still expose a callable ``run`` no-op."""
        process = concurrency.AsyncProcess()

        process.run()
