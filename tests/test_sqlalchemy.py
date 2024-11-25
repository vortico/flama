from unittest.mock import AsyncMock, Mock, call, patch

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction, create_async_engine

from flama import Flama
from flama.client import Client
from flama.exceptions import ApplicationError, SQLAlchemyError
from flama.sqlalchemy import ConnectionManager, MultipleConnectionManager, SingleConnectionManager, SQLAlchemyModule


@pytest.fixture(scope="function")
async def app():
    return Flama(modules={SQLAlchemyModule("sqlite+aiosqlite://")})


@pytest.fixture(scope="function")
def engine():
    return create_async_engine("sqlite+aiosqlite://")


class TestCaseSingleConnectionManager:
    @pytest.fixture(scope="function")
    def connection_manager(self, engine):
        return SingleConnectionManager(engine)

    @pytest.fixture(scope="function")
    async def connection(self, connection_manager):
        c = await connection_manager.open()

        yield c

        await connection_manager.close(c)

    def test_init(self, engine):
        connection_manager = SingleConnectionManager(engine)

        assert connection_manager._connection is None
        assert connection_manager._transaction is None
        assert connection_manager._connection_clients == 0

    def test_connection_not_initialized(self, connection_manager):
        with pytest.raises(SQLAlchemyError, match="Connection not initialized"):
            connection_manager.connection

    def test_transaction_not_initialized(self, connection_manager):
        with pytest.raises(SQLAlchemyError, match="Transaction not started"):
            connection_manager.transaction

    async def test_open_close_connection(self, connection_manager):
        assert connection_manager._connection_clients == 0
        assert connection_manager._connection is None

        first_connection = await connection_manager.open()

        assert connection_manager._connection_clients == 1
        assert connection_manager._connection == first_connection

        second_connection = await connection_manager.open()

        assert first_connection == second_connection
        assert connection_manager._connection_clients == 2
        assert connection_manager._connection == second_connection

        # Close a wrong connection
        with pytest.raises(SQLAlchemyError, match="Wrong connection"):
            await connection_manager.close(Mock(spec=AsyncConnection))

        await connection_manager.close(second_connection)

        assert connection_manager._connection_clients == 1
        assert connection_manager._connection == first_connection

        await connection_manager.close(first_connection)

        assert connection_manager._connection_clients == 0
        assert connection_manager._connection is None

    @pytest.mark.parametrize(
        ["rollback", "commit_calls", "rollback_calls"],
        (
            pytest.param(False, [call()], [], id="commit"),
            pytest.param(True, [], [call()], id="rollback"),
        ),
    )
    async def test_begin_end_transaction(self, connection_manager, connection, rollback, commit_calls, rollback_calls):
        # Begin a transaction using a wrong connection
        with pytest.raises(SQLAlchemyError, match="Wrong connection"):
            await connection_manager.begin(Mock(spec=AsyncConnection))

        assert connection_manager._transaction_clients == 0
        assert connection_manager._transaction is None

        with patch.multiple("sqlalchemy.ext.asyncio.AsyncTransaction", rollback=AsyncMock(), commit=AsyncMock()):
            first_transaction = await connection_manager.begin(connection)

            assert connection_manager._transaction_clients == 1
            assert connection_manager._transaction == first_transaction

            second_transaction = await connection_manager.begin(connection)

            assert first_transaction == second_transaction
            assert connection_manager._transaction_clients == 2
            assert connection_manager._transaction == first_transaction

            # Close a transaction using a wrong transaction
            with pytest.raises(SQLAlchemyError, match="Wrong transaction"):
                await connection_manager.end(Mock(spec=AsyncTransaction))

            await connection_manager.end(second_transaction, rollback=rollback)

            assert second_transaction.commit.call_args_list == []
            assert second_transaction.rollback.call_args_list == []
            assert connection_manager._transaction_clients == 1
            assert connection_manager._transaction == first_transaction

            await connection_manager.end(first_transaction, rollback=rollback)

            assert first_transaction.commit.call_args_list == commit_calls
            assert first_transaction.rollback.call_args_list == rollback_calls
            assert connection_manager._transaction_clients == 0
            assert connection_manager._transaction is None


class TestCaseMultipleConnectionManager:
    @pytest.fixture(scope="function")
    def connection_manager(self, engine):
        return MultipleConnectionManager(engine)

    def test_init(self, engine):
        connection_manager = MultipleConnectionManager(engine)

        assert connection_manager._connections == set()
        assert connection_manager._transactions == {}

    async def test_open_close_connection(self, connection_manager):
        assert connection_manager._connections == set()

        first_connection = await connection_manager.open()

        assert connection_manager._connections == {first_connection}

        second_connection = await connection_manager.open()

        assert first_connection != second_connection
        assert connection_manager._connections == {first_connection, second_connection}

        # Close an uninitialized connection
        with pytest.raises(SQLAlchemyError, match="Connection not initialized"):
            await connection_manager.close(Mock(spec=AsyncConnection))

        await connection_manager.close(second_connection)

        assert connection_manager._connections == {first_connection}

        await connection_manager.close(first_connection)

        assert connection_manager._connections == set()

    @pytest.mark.parametrize(
        ["rollback", "commit_calls", "rollback_calls"],
        (
            pytest.param(False, [call()], [], id="commit"),
            pytest.param(True, [], [call()], id="rollback"),
        ),
    )
    async def test_begin_end_transaction(self, connection_manager, rollback, commit_calls, rollback_calls):
        assert connection_manager._connections == set()
        assert connection_manager._transactions == {}

        # Begin a transaction using a wrong connection
        with pytest.raises(SQLAlchemyError, match="Connection not initialized"):
            await connection_manager.begin(Mock(spec=AsyncConnection))

        # Close a transaction that is not started
        with pytest.raises(SQLAlchemyError, match="Transaction not started"):
            await connection_manager.end(Mock(spec=AsyncTransaction))

        with patch.multiple("sqlalchemy.ext.asyncio.AsyncTransaction", rollback=AsyncMock(), commit=AsyncMock()):
            first_connection = await connection_manager.open()
            second_connection = await connection_manager.open()
            first_connection_transaction = await connection_manager.begin(first_connection)
            second_connection_transaction = await connection_manager.begin(second_connection)

            # Two transactions for the same connection
            with pytest.raises(SQLAlchemyError, match="Transaction already started in this connection"):
                await connection_manager.begin(first_connection)

            assert connection_manager._connections == {first_connection, second_connection}
            assert connection_manager._transactions == {
                first_connection: first_connection_transaction,
                second_connection: second_connection_transaction,
            }

            await connection_manager.end(second_connection_transaction, rollback=rollback)
            assert second_connection_transaction.commit.call_args_list == commit_calls
            assert second_connection_transaction.rollback.call_args_list == rollback_calls

            assert connection_manager._transactions == {first_connection: first_connection_transaction}

            await connection_manager.close(first_connection)

            assert connection_manager._connections == {second_connection}
            assert connection_manager._transactions == {}

            await connection_manager.close(second_connection)

            assert connection_manager._connections == set()
            assert connection_manager._transactions == {}


class TestCaseSQLAlchemyModule:
    @pytest.mark.parametrize(
        ["uri", "exception"],
        (
            pytest.param("sqlite+aiosqlite://", None, id="sqlite"),
            pytest.param(None, ApplicationError("Database connection string must be provided"), id="no_database"),
        ),
        indirect=["exception"],
    )
    async def test_lifespan_cycle(self, uri, exception):
        with exception:
            app = Flama(modules={SQLAlchemyModule(uri)})
            async with Client(app):  # Initialize app life-cycle
                assert app.sqlalchemy.database == uri
                assert isinstance(app.sqlalchemy.metadata, sqlalchemy.MetaData)
                assert isinstance(app.sqlalchemy._engine, AsyncEngine)
                assert isinstance(app.sqlalchemy._connection_manager, ConnectionManager)

            assert app.sqlalchemy.database == uri
            assert isinstance(app.sqlalchemy.metadata, sqlalchemy.MetaData)
            assert app.sqlalchemy._engine is None
            assert app.sqlalchemy._connection_manager is None

    def test_engine_not_initialized(self, app):
        with pytest.raises(ApplicationError, match="SQLAlchemyModule not initialized"):
            app.sqlalchemy.engine

    def test_connection_manager_not_initialized(self, app):
        with pytest.raises(ApplicationError, match="SQLAlchemyModule not initialized"):
            app.sqlalchemy.connection_manager

    async def test_open_connection(self, app):
        connection_manager_mock = AsyncMock(spec=ConnectionManager)

        with patch.object(app.sqlalchemy, "_connection_manager", connection_manager_mock):
            await app.sqlalchemy.open_connection()

        assert connection_manager_mock.open.await_args_list == [call()]

    async def test_close_connection(self, app):
        connection_manager_mock = AsyncMock(spec=ConnectionManager)
        connection_mock = Mock(spec=AsyncConnection)

        with patch.object(app.sqlalchemy, "_connection_manager", connection_manager_mock):
            await app.sqlalchemy.close_connection(connection_mock)

        assert connection_manager_mock.close.await_args_list == [call(connection_mock)]

    async def test_begin_transaction(self, app):
        connection_manager_mock = AsyncMock(spec=ConnectionManager)
        connection_mock = Mock(spec=AsyncConnection)

        with patch.object(app.sqlalchemy, "_connection_manager", connection_manager_mock):
            await app.sqlalchemy.begin_transaction(connection_mock)

        assert connection_manager_mock.begin.await_args_list == [call(connection_mock)]

    async def test_end_transaction(self, app):
        connection_manager_mock = AsyncMock(spec=ConnectionManager)
        transaction_mock = Mock(spec=AsyncTransaction)

        with patch.object(app.sqlalchemy, "_connection_manager", connection_manager_mock):
            await app.sqlalchemy.end_transaction(transaction_mock)

        assert connection_manager_mock.end.await_args_list == [call(transaction_mock, rollback=False)]
