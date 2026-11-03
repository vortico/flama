import typing as t
from unittest.mock import AsyncMock, call, patch

import pytest

from flama.ddd.repositories._base import BaseRepository
from flama.ddd.workers import _base as workers_base
from flama.ddd.workers._base import AbstractWorker, BaseWorker
from flama.exceptions import ApplicationError

T = t.TypeVar("T")


class StringRepository(BaseRepository): ...


class GenericRepository(BaseRepository, t.Generic[T]): ...


@pytest.fixture(scope="function")
def repository():
    class FooRepository(BaseRepository): ...

    return FooRepository


@pytest.fixture(scope="function")
def base_worker():
    class Worker(BaseWorker):
        async def set_up(self): ...

        async def tear_down(self, *, rollback: bool = False): ...

        async def repository_params(self):
            return [], {}

        async def commit(self): ...

        async def rollback(self): ...

    return Worker


class TestCaseAbstractWorker:
    @pytest.fixture(scope="function")
    def worker(self):
        class FooWorker(AbstractWorker):
            async def begin(self): ...

            async def end(self, *, rollback: bool = False): ...

            async def commit(self): ...

            async def rollback(self): ...

        return FooWorker()

    def test_app(self, app, worker):
        with pytest.raises(ApplicationError, match="Worker not initialized"):
            worker.app

        worker.app = app

        assert worker.app == app

        del worker.app

        with pytest.raises(ApplicationError, match="Worker not initialized"):
            worker.app

    async def test_async_context(self, app, worker):
        worker.app = app

        with patch.multiple(worker, begin=AsyncMock(), end=AsyncMock()):
            async with worker:
                assert worker.begin.await_args_list == [call()]
                assert worker.end.await_args_list == []

            assert worker.begin.await_args_list == [call()]
            assert worker.end.await_args_list == [call(rollback=False)]


class TestCaseBaseWorker:
    @pytest.fixture(
        scope="function",
        params=[
            pytest.param("direct", id="direct_annotations"),
            pytest.param("child_fallback", id="fallback_when_get_annotations_raises"),
        ],
    )
    def worker(self, request, repository):
        class FooWorker(BaseWorker):
            foo: repository
            bar: "int"

            async def set_up(self): ...

            async def tear_down(self, *, rollback: bool = False): ...

            async def repository_params(self):
                return [], {}

            async def begin(self): ...

            async def end(self, *, rollback: bool = False): ...

            async def commit(self): ...

            async def rollback(self): ...

        if request.param == "direct":
            return FooWorker, {"foo": repository}
        if request.param == "child_fallback":
            with patch.object(
                workers_base.compat, "get_annotations", side_effect=ValueError("unresolvable annotation")
            ):

                class Child(FooWorker): ...

            return Child, {"foo": repository}

    def test_new(self, worker):
        worker_cls, expected_repos = worker

        assert hasattr(worker_cls, "_repositories")
        assert worker_cls._repositories == expected_repos

    def test_new_classifies_annotations(self, base_worker, repository):
        class Worker(base_worker):
            foo: GenericRepository[int]
            bar: list[int]
            baz: repository | None
            qux: int

        assert Worker._repositories == {"foo": GenericRepository[int]}
        assert Worker.__annotations__ == {"bar": list[int], "baz": repository | None, "qux": int}

    def test_new_resolves_string_annotations(self, base_worker):
        class Worker(base_worker):
            foo: "StringRepository"
            bar: "Missing"  # noqa: F821

        assert Worker._repositories == {"foo": StringRepository}
        assert Worker.__annotations__ == {"bar": "Missing"}

    def test_new_inherits_repositories(self, base_worker, repository):
        class OtherRepository(BaseRepository): ...

        class Worker(base_worker):
            foo: repository
            bar: repository

        class Child(Worker): ...

        class ChildWithOwn(Worker):
            baz: OtherRepository

        class ChildOverriding(Worker):
            foo: OtherRepository
            bar: int

        assert Child._repositories == {"foo": repository, "bar": repository}
        assert ChildWithOwn._repositories == {"foo": repository, "bar": repository, "baz": OtherRepository}
        assert ChildOverriding._repositories == {"foo": OtherRepository}

    async def test_begin_parameterised_repository(self, base_worker):
        class Worker(base_worker):
            foo: GenericRepository[int]

        worker = Worker()

        await worker.begin()

        assert isinstance(worker.foo, GenericRepository)
        assert worker.foo.__orig_class__ == GenericRepository[int]

    def test_new_skips_base(self):
        class MockBase(AbstractWorker, metaclass=workers_base.WorkerType):
            __module__ = "flama.ddd.workers"
            __qualname__ = "BaseWorker"

            async def begin(self): ...

            async def end(self, *, rollback=False): ...

            async def commit(self): ...

            async def rollback(self): ...

        assert not hasattr(MockBase, "_repositories")
