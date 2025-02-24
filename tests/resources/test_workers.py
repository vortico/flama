import pytest

from flama import Flama
from flama.client import Client
from flama.ddd.repositories import HTTPRepository
from flama.ddd.repositories.sqlalchemy import SQLAlchemyRepository
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
        class FooWorker(FlamaWorker): ...

        return FooWorker()

    @pytest.fixture(scope="function")
    def sqlalchemy_repository(self):
        class FooRepository(SQLAlchemyRepository): ...

        return FooRepository

    @pytest.fixture(scope="function")
    def http_repository(self):
        class BarRepository(HTTPRepository): ...

        return BarRepository

    def test_init(self):
        worker = FlamaWorker()

        assert not worker._resources_repositories.registered

    async def test_async_context(self, app, worker, http_repository, sqlalchemy_repository):
        worker.app = app
        worker.add_repository("foo", sqlalchemy_repository)
        worker.add_repository("bar", http_repository)

        with pytest.raises(ApplicationError, match="Repositories not initialized"):
            worker.repositories

        async with worker:
            assert worker.repositories == {
                "foo": sqlalchemy_repository(worker.connection),
                "bar": http_repository(worker.connection),
            }

        worker.remove_repository("bar")

        async with worker:
            assert worker.repositories == {"foo": sqlalchemy_repository(worker.connection)}
