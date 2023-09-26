from unittest.mock import Mock

import pytest
import sqlalchemy

from flama import Flama
from flama.ddd import SQLAlchemyRepository
from flama.resources.workers import FlamaWorker
from flama.sqlalchemy import SQLAlchemyModule


class TestCaseFlamaWorker:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})

    @pytest.fixture(scope="function")
    def worker(self, client):
        return FlamaWorker(client.app)

    @pytest.fixture(scope="function")
    def repository(self):
        class FooRepository(SQLAlchemyRepository):
            _table = Mock(spec=sqlalchemy.Table)

        return FooRepository

    def test_init(self, app):
        worker = FlamaWorker()

        assert not worker._init_repositories

    def test_add_repository(self, worker, repository):
        assert worker._repositories == {}

        worker.add_repository("foo", repository)

        assert worker._repositories == {"foo": repository}

    async def test_async_context(self, worker, repository):
        worker.add_repository("foo", repository)

        with pytest.raises(AssertionError, match="Repositories not initialized"):
            worker.repositories

        async with worker:
            assert worker.repositories == {"foo": repository(worker.connection)}
