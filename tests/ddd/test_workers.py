from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from flama import Flama
from flama.ddd import AbstractWorker, SQLAlchemyRepository, SQLAlchemyWorker, WorkerType
from flama.ddd.repositories import AbstractRepository
from flama.sqlalchemy import SQLAlchemyModule


class TestCaseSQLAlchemyWorker:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})

    @pytest.fixture(scope="function")
    def worker(self, client):
        class FooWorker(SQLAlchemyWorker):
            bar: SQLAlchemyRepository

        return FooWorker(client.app)

    def test_init(self, app):
        worker = SQLAlchemyWorker(app)

        assert worker._app == app
        assert not hasattr(worker, "_connection")

    def test_app(self, app):
        worker = SQLAlchemyWorker()

        with pytest.raises(AssertionError, match="Worker not initialized"):
            worker.app

        worker.app = app

        assert worker.app == app

        del worker.app

        with pytest.raises(AssertionError, match="Worker not initialized"):
            worker.app

    def test_connection(self, worker):
        with pytest.raises(AttributeError, match="Connection not initialized"):
            worker.connection

    async def test_begin(self, worker):
        transaction_mock = AsyncMock(spec=AsyncTransaction)
        connection_mock = AsyncMock(spec=AsyncConnection)
        connection_mock.begin = transaction_mock
        engine_mock = MagicMock(spec=AsyncEngine)
        engine_mock.connect.return_value = connection_mock

        with patch.object(worker.app.sqlalchemy, "engine", new=engine_mock):
            await worker.begin()
            assert engine_mock.connect.call_args_list == [call()]
            assert connection_mock.__aenter__.await_args_list == [call()]
            assert connection_mock.begin.call_args_list == [call()]
            assert connection_mock.begin.await_args_list == [call()]

    async def test_close(self, worker):
        assert not hasattr(worker, "_transaction")
        assert not hasattr(worker, "_connection")

        connection_mock = AsyncMock(spec=AsyncConnection)
        transaction_mock = AsyncMock(spec=AsyncTransaction)
        worker._connection = connection_mock
        worker._transaction = transaction_mock

        await worker.close()

        assert transaction_mock.__aexit__.await_args_list == [call(None, None, None)]
        assert connection_mock.__aexit__.await_args_list == [call(None, None, None)]
        assert not hasattr(worker, "_transaction")
        assert not hasattr(worker, "_connection")

    async def test_async_context(self, worker):
        assert not hasattr(worker, "_transaction")
        assert not hasattr(worker, "_connection")
        assert not hasattr(worker, "bar")

        async with worker:
            assert worker._connection
            assert worker._transaction
            assert worker._transaction.is_active
            assert hasattr(worker, "bar")
            assert isinstance(worker.bar, SQLAlchemyRepository)

        assert not hasattr(worker, "_transaction")
        assert not hasattr(worker, "_connection")
        assert not hasattr(worker, "bar")

    async def test_commit(self, worker):
        commit_mock = AsyncMock()
        connection_mock = AsyncMock(spec=AsyncConnection)
        connection_mock.commit = commit_mock

        with patch.object(worker, "_connection", new=connection_mock, create=True):
            await worker.commit()
            assert commit_mock.await_args_list == [call()]

    async def test_rollback(self, worker):
        rollback_mock = AsyncMock()
        connection_mock = AsyncMock(spec=AsyncConnection)
        connection_mock.rollback = rollback_mock

        with patch.object(worker, "_connection", new=connection_mock, create=True):
            await worker.rollback()
            assert rollback_mock.await_args_list == [call()]


class TestCaseWorkerType:
    @pytest.fixture(scope="function")
    def worker(self):
        class Worker(AbstractWorker):
            async def __aenter__(self) -> "Worker":
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            async def commit(self) -> None:
                ...

            async def rollback(self) -> None:
                ...

        return Worker

    @pytest.fixture(scope="function")
    def repository(self):
        class Repository(AbstractRepository):
            ...

        return Repository

    def test_custom_worker(self, worker, repository):
        class CustomWorker(worker, metaclass=WorkerType):
            foo: repository

        assert CustomWorker._repositories == {"foo": repository}
