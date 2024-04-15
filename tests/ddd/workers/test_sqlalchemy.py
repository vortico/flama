from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from flama.ddd.repositories import SQLAlchemyRepository
from flama.ddd.workers import SQLAlchemyWorker


class TestCaseSQLAlchemyWorker:
    @pytest.fixture(scope="function")
    def worker(self, client):
        class FooWorker(SQLAlchemyWorker):
            bar: SQLAlchemyRepository

        return FooWorker(client.app)

    def test_init(self, app):
        worker = SQLAlchemyWorker(app)

        assert worker._app == app
        assert not hasattr(worker, "_connection")

    def test_connection(self, worker):
        with pytest.raises(AttributeError, match="Connection not initialized"):
            worker.connection

    def test_transaction(self, worker):
        with pytest.raises(AttributeError, match="Transaction not started"):
            worker.transaction

    async def test_begin_transaction(self, app, worker):
        connection_mock = AsyncMock()
        transaction_mock = AsyncMock()

        with patch.multiple(
            app.sqlalchemy,
            open_connection=AsyncMock(return_value=connection_mock),
            begin_transaction=AsyncMock(return_value=transaction_mock),
        ):
            await worker.begin_transaction()

            assert worker._connection == connection_mock
            assert worker._transaction == transaction_mock
            assert app.sqlalchemy.open_connection.await_args_list == [call()]
            assert app.sqlalchemy.begin_transaction.await_args_list == [call(connection_mock)]

    @pytest.mark.parametrize(
        ["rollback"],
        (
            pytest.param(True, id="rollback"),
            pytest.param(False, id="commit"),
        ),
    )
    async def test_end_transaction(self, app, worker, rollback):
        worker._connection = connection_mock = AsyncMock()
        worker._transaction = transaction_mock = AsyncMock()

        with patch.multiple(app.sqlalchemy, end_transaction=AsyncMock(), close_connection=AsyncMock()):
            await worker.end_transaction(rollback=rollback)

            assert not hasattr(worker, "_transaction")
            assert not hasattr(worker, "_connection")
            assert app.sqlalchemy.end_transaction.await_args_list == [call(transaction_mock, rollback=rollback)]
            assert app.sqlalchemy.close_connection.await_args_list == [call(connection_mock)]

    async def test_begin(self, worker):
        worker._connection = AsyncMock()

        with patch.object(worker, "begin_transaction"):
            assert not hasattr(worker, "bar")

            await worker.begin()

            assert worker.begin_transaction.await_args_list == [call()]
            assert hasattr(worker, "bar")
            assert isinstance(worker.bar, SQLAlchemyRepository)

    @pytest.mark.parametrize(
        ["rollback"],
        (
            pytest.param(True, id="rollback"),
            pytest.param(False, id="commit"),
        ),
    )
    async def test_end(self, worker, rollback):
        worker.bar = MagicMock()

        with patch.object(worker, "end_transaction"):
            assert hasattr(worker, "bar")

            await worker.end(rollback=rollback)

            assert worker.end_transaction.await_args_list == [call(rollback=rollback)]
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
