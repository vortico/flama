import functools

from flama import concurrency


class TestCaseIsAsync:
    def test_function(self):
        def foo_sync():
            ...

        async def foo_async():
            ...

        assert not concurrency.is_async(foo_sync)
        assert concurrency.is_async(foo_async)

    def test_callable(self):
        class FooSync:
            def __call__(self):
                ...

        class FooAsync:
            async def __call__(self):
                ...

        assert not concurrency.is_async(FooSync)
        assert concurrency.is_async(FooAsync)

    def test_partial(self):
        def foo_sync(x: int):
            ...

        partial_foo_sync = functools.partial(foo_sync, x=1)

        async def foo_async(x: int):
            ...

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
