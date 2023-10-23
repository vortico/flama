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

    def test_init(self, engine):
        connection_manager = SingleConnectionManager(engine)

        assert connection_manager._connection is None
        assert connection_manager._transaction is None
        assert connection_manager._clients == 0

    def test_connection_not_initialized(self, connection_manager):
        with pytest.raises(SQLAlchemyError, match="Connection not initialized"):
            connection_manager.connection

    def test_transaction_not_initialized(self, connection_manager):
        with pytest.raises(SQLAlchemyError, match="Transaction not started"):
            connection_manager.transaction

    async def test_open_close_connection(self, connection_manager):
        assert connection_manager._clients == 0
        assert connection_manager._connection is None

        first_connection = await connection_manager.open()

        assert connection_manager._clients == 1
        assert connection_manager._connection == first_connection

        second_connection = await connection_manager.open()

        assert first_connection == second_connection
        assert connection_manager._clients == 2
        assert connection_manager._connection == second_connection

        # Close a wrong connection
        with pytest.raises(SQLAlchemyError, match="Wrong connection"):
            await connection_manager.close(Mock(spec=AsyncConnection))

        await connection_manager.close(second_connection)

        assert connection_manager._clients == 1
        assert connection_manager._connection == first_connection

        await connection_manager.close(first_connection)

        assert connection_manager._clients == 0
        assert connection_manager._connection is None

    async def test_begin_end_transaction(self, connection_manager):
        connection = await connection_manager.open()

        # Begin a transaction using a wrong connection
        with pytest.raises(SQLAlchemyError, match="Wrong connection"):
            await connection_manager.begin(Mock(spec=AsyncConnection))

        assert connection_manager._transaction is None

        main_transaction = await connection_manager.begin(connection)

        assert connection_manager._transaction == main_transaction

        nested_transaction = await connection_manager.begin(connection)

        assert main_transaction != nested_transaction
        assert connection_manager._transaction == main_transaction

        await connection_manager.end(nested_transaction, rollback=True)

        assert connection_manager._transaction == main_transaction

        await connection_manager.end(main_transaction)

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

    async def test_begin_end_transaction(self, connection_manager):
        assert connection_manager._connections == set()
        assert connection_manager._transactions == {}

        # Begin a transaction using a wrong connection
        with pytest.raises(SQLAlchemyError, match="Connection not initialized"):
            await connection_manager.begin(Mock(spec=AsyncConnection))

        # Close a transaction that is not started
        with pytest.raises(SQLAlchemyError, match="Transaction not started"):
            await connection_manager.end(Mock(spec=AsyncTransaction))

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

        await connection_manager.end(second_connection_transaction, rollback=True)

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

    def test_sqlalchemy_not_installed(self):
        with patch("flama.sqlalchemy.sqlalchemy", new=None), pytest.raises(
            ApplicationError, match=r"sqlalchemy\[asyncio\] must be installed to use SQLAlchemyModule"
        ):
            SQLAlchemyModule("")

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
