from unittest.mock import AsyncMock, call, patch

import pytest

from flama.ddd.repositories.base import BaseRepository
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
    @pytest.fixture(scope="function")
    def worker(self, repository):
        class FooWorker(BaseWorker):
            foo: repository

            async def set_up(self): ...

            async def tear_down(self, *, rollback: bool = False): ...

            async def repository_params(self):
                return [], {}

            async def begin(self): ...

            async def end(self, *, rollback: bool = False): ...

            async def commit(self): ...

            async def rollback(self): ...

        return FooWorker()

    def test_new(self, worker, repository):
        assert hasattr(worker, "_repositories")
        assert worker._repositories == {"foo": repository}
