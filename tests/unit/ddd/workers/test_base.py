from unittest.mock import AsyncMock, call, patch

import pytest

from flama.ddd.repositories.base import BaseRepository
from flama.ddd.workers import base as workers_base
from flama.ddd.workers.base import AbstractWorker, BaseWorker
from flama.exceptions import ApplicationError


@pytest.fixture(scope="function")
def repository():
    class FooRepository(BaseRepository): ...

    return FooRepository


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

            return Child, {}

    def test_new(self, worker):
        worker_cls, expected_repos = worker

        assert hasattr(worker_cls, "_repositories")
        assert worker_cls._repositories == expected_repos

    def test_new_skips_base(self):
        class MockBase(AbstractWorker, metaclass=workers_base.WorkerType):
            __module__ = "flama.ddd.workers"
            __qualname__ = "BaseWorker"

            async def begin(self): ...

            async def end(self, *, rollback=False): ...

            async def commit(self): ...

            async def rollback(self): ...

        assert not hasattr(MockBase, "_repositories")
