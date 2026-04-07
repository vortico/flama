import functools
import multiprocessing
import warnings

import pytest

from flama import concurrency


def sync_event_task(event):
    event.set()


async def async_event_task(event):
    event.set()


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
