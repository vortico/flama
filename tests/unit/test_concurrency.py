import functools
import multiprocessing
import warnings

import pytest

from flama import concurrency


def sync_event_task(event):
    event.set()


async def async_event_task(event):
    event.set()


class TestCaseFileReader:
    @pytest.mark.parametrize(
        ["content", "expected_result", "chunk_size", "start", "end"],
        (
            pytest.param(b"foobar", b"foobar", 64, None, None, id="full"),
            pytest.param(b"foobar", b"oba", 64, 2, 5, id="range"),
            pytest.param(b"foobar", b"foobar", 1, None, None, id="chunks"),
            pytest.param(b"0123456789", b"0123456789", 4, 0, 10, id="range_multi_chunk"),
            pytest.param(b"", b"", 64, None, None, id="empty"),
        ),
    )
    async def test_read(self, tmp_path, content, chunk_size, start, end, expected_result):
        f = tmp_path / "data.bin"
        f.write_bytes(content)

        result = bytearray()
        async with concurrency.FileReader(str(f), chunk_size=chunk_size, start=start, end=end) as reader:
            async for chunk in reader:
                result.extend(chunk)

        assert bytes(result) == expected_result

    async def test_aclose_cancels_producer(self, tmp_path):
        f = tmp_path / "large.bin"
        f.write_bytes(b"a" * 1024)

        async with concurrency.FileReader(str(f), chunk_size=64) as reader:
            async for chunk in reader:
                assert len(chunk) > 0
                break

        assert reader._task is not None
        assert reader._task.done()

    async def test_aclose_noop_after_full_read(self, tmp_path):
        f = tmp_path / "small.bin"
        f.write_bytes(b"hello")

        async with concurrency.FileReader(str(f), chunk_size=64) as reader:
            async for _ in reader:
                pass

        await reader.aclose()

        assert reader._task is not None
        assert reader._task.done()

    async def test_aclose_noop_before_iter(self):
        reader = concurrency.FileReader("/dev/null", chunk_size=64)

        await reader.aclose()

        assert reader._task is None


class TestCaseIterateInThreadpool:
    async def test_iter(self):
        assert [x async for x in concurrency.iterate_in_threadpool([1, 2, 3])] == [1, 2, 3]


class TestCaseIsAsync:
    def test_function(self):
        def foo_sync(): ...

        async def foo_async(): ...

        assert not concurrency.is_async(foo_sync)
        assert concurrency.is_async(foo_async)

    def test_callable(self):
        class FooSync:
            def __call__(self): ...

        class FooAsync:
            async def __call__(self): ...

        assert not concurrency.is_async(FooSync)
        assert concurrency.is_async(FooAsync)

    def test_partial(self):
        def foo_sync(x: int): ...

        partial_foo_sync = functools.partial(foo_sync, x=1)

        async def foo_async(x: int): ...

        partial_foo_async = functools.partial(foo_async, x=1)

        assert not concurrency.is_async(partial_foo_sync)
        assert concurrency.is_async(partial_foo_async)


class TestCaseRun:
    async def test_async(self):
        async def foo_async(x: int):
            return x + 2

        assert await concurrency.run(foo_async, 3) == 5

    async def test_sync(self):
        def foo_sync(x: int):
            return x * 2

        assert await concurrency.run(foo_sync, 3) == 6


class TestCaseRunTaskGroup:
    async def test_run_task_group(self):
        expected_result = ["foo", "bar"]

        async def foo():
            return "foo"

        async def bar():
            return "bar"

        result = [t.result() for t in await concurrency.run_task_group(foo(), bar())]

        assert result == expected_result


class TestCaseAsyncProcess:
    @pytest.mark.parametrize(
        ["target"],
        (
            pytest.param(sync_event_task, id="sync"),
            pytest.param(async_event_task, id="async"),
            pytest.param(None, id="no_target"),
        ),
    )
    async def test_async_process(self, target):
        event = multiprocessing.Event()

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            process = concurrency.AsyncProcess(target=target, args=(event,))
            process.start()
            process.join()

        if target:
            assert event.wait(5.0)
