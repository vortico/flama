import pytest

from flama import Flama
from flama.client import Client
from flama.ddd.repositories import SQLAlchemyRepository
from flama.exceptions import ApplicationError
from flama.resources.workers import FlamaWorker
from flama.sqlalchemy import SQLAlchemyModule


class TestCaseFlamaWorker:
    @pytest.fixture(scope="function")
    async def app(self):
        app_ = Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})
        async with Client(app_):
            yield app_

    @pytest.fixture(scope="function")
    def worker(self):
        class FooWorker(FlamaWorker):
            ...

        return FooWorker()

    @pytest.fixture(scope="function")
    def repository(self):
        class FooRepository(SQLAlchemyRepository):
            ...

        return FooRepository

    def test_init(self):
        worker = FlamaWorker()

        assert not worker._init_repositories

    def test_add_repository(self, worker, repository):
        assert worker._repositories == {}

        worker.add_repository("foo", repository)

        assert worker._repositories == {"foo": repository}

    async def test_async_context(self, app, worker, repository):
        worker.app = app
        worker.add_repository("foo", repository)

        with pytest.raises(ApplicationError, match="Repositories not initialized"):
            worker.repositories

        async with worker:
            assert worker.repositories == {"foo": repository(worker.connection)}
