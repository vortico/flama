import abc
import logging
import typing as t

from flama import exceptions
from flama.modules import Module

try:
    import sqlalchemy
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction, create_async_engine

    metadata = sqlalchemy.MetaData()
except Exception:  # pragma: no cover
    raise exceptions.DependencyNotInstalled(
        dependency=exceptions.DependencyNotInstalled.Dependency.sqlalchemy, dependant=__name__
    )


__all__ = ["metadata", "SQLAlchemyModule"]

logger = logging.getLogger(__name__)


class ConnectionManager(abc.ABC):
    """Abstract class for connection managers.

    It will be used to manage the connections and transactions.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        """Initialize the connection manager.

        :param engine: SQLAlchemy engine.
        """
        self._engine = engine

    @abc.abstractmethod
    async def open(self) -> AsyncConnection:
        """Open a new connection to the database.

        :return: Database connection.
        """
        ...

    @abc.abstractmethod
    async def close(self, connection: AsyncConnection) -> None:
        """Close the connection to the database.

        :param connection: Database connection.
        """
        ...

    @abc.abstractmethod
    async def begin(self, connection: AsyncConnection) -> AsyncTransaction:
        """Begin a new transaction.

        :param connection: Database connection to use for the transaction.
        :return: Database transaction.
        """
        ...

    @abc.abstractmethod
    async def end(self, transaction: AsyncTransaction, *, rollback: bool = False) -> None:
        """End a transaction.

        :param transaction: Database transaction.
        :param rollback: If the transaction should be rolled back.
        """
        ...


class SingleConnectionManager(ConnectionManager):
    """Connection manager that uses a single connection and transaction.

    A single connection is opened when requested, and subsequent requests will share this same connection. Once all
    clients finishes with the connection, it will be closed.

    The transaction is similar to the transaction, but it will be created at first request and subsequent requests will
    generate a nested transaction.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        """Initialize the connection manager.

        :param engine: SQLAlchemy engine.
        """
        super().__init__(engine)
        self._connection: t.Optional[AsyncConnection] = None
        self._transaction: t.Optional[AsyncTransaction] = None
        self._connection_clients = 0
        self._transaction_clients = 0

    @property
    def connection(self) -> AsyncConnection:
        """Connection to the database.

        :return: Connection to the database.
        :raises SQLAlchemyError: If the connection is not initialized.
        """
        if not self._connection:
            raise exceptions.SQLAlchemyError("Connection not initialized")

        return self._connection

    @property
    def transaction(self) -> AsyncTransaction:
        """Transaction to the database.

        :return: Transaction to the database.
        :raises SQLAlchemyError: If the transaction is not initialized.
        """
        if not self._transaction:
            raise exceptions.SQLAlchemyError("Transaction not started")

        return self._transaction

    async def open(self) -> AsyncConnection:
        """Open a new connection to the database.

        The first client will open a new connection, and subsequent clients will share this same connection.

        :return: Database connection.
        """
        try:
            connection = self.connection
        except exceptions.SQLAlchemyError:
            self._connection = connection = self._engine.connect()
            await self._connection.__aenter__()

        self._connection_clients += 1
        return connection

    async def close(self, connection: AsyncConnection) -> None:
        """Close the connection to the database.

        If this is the last client, the connection will be closed.

        :param connection: Database connection.
        :raises SQLAlchemyError: If the connection is a different connection from the one opened.
        """
        if connection != self.connection:
            raise exceptions.SQLAlchemyError("Wrong connection")

        self._connection_clients -= 1

        if self._connection_clients == 0:
            await connection.__aexit__(None, None, None)
            self._connection = None

    async def begin(self, connection: AsyncConnection) -> AsyncTransaction:
        """Begin a new transaction.

        The first client will create a new transaction, and subsequent clients will share this same transaction.

        :return: Database transaction.
        :raises SQLAlchemyError: If the connection is a different connection from the one opened.
        """
        if connection != self.connection:
            raise exceptions.SQLAlchemyError("Wrong connection")

        try:
            transaction = self.transaction
        except exceptions.SQLAlchemyError:
            self._transaction = transaction = connection.begin()
            await transaction

        self._transaction_clients += 1
        return transaction

    async def end(self, transaction: AsyncTransaction, *, rollback: bool = False) -> None:
        """End a transaction.

        If this is the last client, the connection will be committed or rolled back.

        :param transaction: Database transaction.
        :param rollback: If the transaction should be rolled back.
        """
        if transaction != self.transaction:
            raise exceptions.SQLAlchemyError("Wrong transaction")

        self._transaction_clients -= 1

        if self._transaction_clients == 0:
            if rollback:
                await transaction.rollback()
            else:
                await transaction.commit()

            self._transaction = None


class MultipleConnectionManager(ConnectionManager):
    """Connection manager that handlers several connections and transactions."""

    def __init__(self, engine: AsyncEngine) -> None:
        """Initialize the connection manager.

        This manager keeps track of the connections and transactions, and it will close the connections when requested.
        If a connection is closed, all their transactions will be commited and finished too.

        :param engine: SQLAlchemy engine.
        """
        super().__init__(engine)
        self._connections: set[AsyncConnection] = set()
        self._transactions: dict[AsyncConnection, AsyncTransaction] = {}

    async def open(self) -> AsyncConnection:
        """Open a new connection to the database.

        :return: Database connection.
        """
        connection = self._engine.connect()
        await connection.start()
        self._connections.add(connection)
        return connection

    async def close(self, connection: AsyncConnection) -> None:
        """Close the connection to the database.

        :param connection: Database connection.
        :raises SQLAlchemyError: If the connection is not initialized.
        """
        if connection not in self._connections:
            raise exceptions.SQLAlchemyError("Connection not initialized")

        if connection in self._transactions:
            await self.end(self._transactions[connection])

        self._connections.remove(connection)
        await connection.close()

    async def begin(self, connection: AsyncConnection) -> AsyncTransaction:
        """Begin a new transaction.

        :param connection: Database connection to use for the transaction.
        :return: Database transaction.
        :raises SQLAlchemyError: If the connection is not initialized.
        """
        if connection not in self._connections:
            raise exceptions.SQLAlchemyError("Connection not initialized")

        if connection in self._transactions:
            raise exceptions.SQLAlchemyError("Transaction already started in this connection")

        transaction = await connection.begin()
        self._transactions[connection] = transaction
        return transaction

    async def end(self, transaction: AsyncTransaction, *, rollback: bool = False) -> None:
        """End a transaction.

        :param transaction: Database transaction.
        :param rollback: If the transaction should be rolled back.
        :raises SQLAlchemyError: If the transaction is not started.
        """
        if transaction.connection not in self._transactions:
            raise exceptions.SQLAlchemyError("Transaction not started")

        del self._transactions[transaction.connection]

        if rollback:
            await transaction.rollback()
        else:
            await transaction.commit()


class SQLAlchemyModule(Module):
    """SQLAlchemy module.

    It will initialize the SQLAlchemy engine and connection manager. It will also provide an interface to handle
    connections and transactions.

    Referring to how connections and transactions are managed, it can work in two modes: single connection and multiple
    connections.
    * Multiple connections (default): It will open a new connection and transaction for each request. It will keep
    track of the connections, and it will close it when requested. Multiple transactions using the same connection is
    also supported.
    * Single connection: It will open a single connection and transaction, and all requests will share this connection
    and transaction. The connection will be closed when all clients finishes. It will create a single transaction and
    new transactions requested will be nested from this one.
    """

    name = "sqlalchemy"

    def __init__(
        self, database: str, single_connection: bool = False, engine_args: t.Optional[dict[str, t.Any]] = None
    ):
        """Initialize the SQLAlchemy module.

        Referring to how connections and transactions are managed, it can work in two modes: single connection and
        multiple connections.
        * Multiple connections (default): It will open a new connection and transaction for each request. It will keep
        track of the connections, and it will close it when requested. Multiple transactions using the same connection
        is also supported.
        * Single connection: It will open a single connection and transaction, and all requests will share this
        connection and transaction. The connection will be closed when all clients finishes. It will create a single
        transaction and new transactions requested will be nested from this one.

        :param database: Database connection string.
        :param single_connection: If the module should work in single connection mode.
        :param engine_args: Arguments to pass to the SQLAlchemy engine.
        :raises ApplicationError: If SQLAlchemy is not installed.
        """
        if not database:
            raise exceptions.ApplicationError("Database connection string must be provided")

        super().__init__()

        self.database = database
        self.metadata: sqlalchemy.MetaData = metadata
        self._engine: t.Optional[AsyncEngine] = None
        self._engine_args = engine_args or {}
        self._connection_manager: t.Optional[ConnectionManager] = None
        self._manager_cls: type[ConnectionManager] = (
            SingleConnectionManager if single_connection else MultipleConnectionManager
        )

    @property
    def engine(self) -> AsyncEngine:
        """SQLAlchemy engine.

        :return: SQLAlchemy engine.
        :raises ApplicationError: If SQLAlchemyModule is not initialized.
        """
        if self._engine is None:
            raise exceptions.ApplicationError("SQLAlchemyModule not initialized")
        return self._engine

    @property
    def connection_manager(self) -> "ConnectionManager":
        """Connection manager.

        :return: Connection manager.
        :raises ApplicationError: If SQLAlchemyModule is not initialized.
        """
        if self._connection_manager is None:
            raise exceptions.ApplicationError("SQLAlchemyModule not initialized")
        return self._connection_manager

    async def open_connection(self) -> AsyncConnection:
        """Open a new connection to the database.

        :return: Database connection.
        """
        return await self.connection_manager.open()

    async def close_connection(self, connection: AsyncConnection) -> None:
        """Close the connection to the database.

        :param connection: Database connection.
        """
        return await self.connection_manager.close(connection)

    async def begin_transaction(self, connection: AsyncConnection) -> AsyncTransaction:
        """Begin a new transaction.

        :param connection: Database connection to use for the transaction.
        :return: Database transaction.
        """
        return await self.connection_manager.begin(connection)

    async def end_transaction(self, transaction: AsyncTransaction, *, rollback: bool = False) -> None:
        """End a transaction.

        :param transaction: Database transaction.
        :param rollback: If the transaction should be rolled back.
        :return: Database transaction.
        """
        return await self.connection_manager.end(transaction, rollback=rollback)

    async def on_startup(self):
        """Initialize the SQLAlchemy engine and connection manager."""
        self._engine = create_async_engine(self.database, **self._engine_args)
        self._connection_manager = self._manager_cls(self._engine)

    async def on_shutdown(self):
        """Close the SQLAlchemy engine and connection manager."""
        await self.engine.dispose()
        self._engine = None
        self._connection_manager = None
