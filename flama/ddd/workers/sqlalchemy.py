import logging
import typing as t

from flama.ddd.workers.base import AbstractWorker

if t.TYPE_CHECKING:
    try:
        from sqlalchemy.ext.asyncio import AsyncConnection, AsyncTransaction
    except Exception:  # pragma: no cover
        ...

__all__ = ["SQLAlchemyWorker"]

logger = logging.getLogger(__name__)


class SQLAlchemyWorker(AbstractWorker):
    """Worker for SQLAlchemy.

    It will provide a connection and a transaction to the database and create the repositories for the entities.
    """

    _connection: "AsyncConnection"
    _transaction: "AsyncTransaction"

    @property
    def connection(self) -> "AsyncConnection":
        """Connection to the database.

        :return: Connection to the database.
        :raises AttributeError: If the connection is not initialized.
        """
        try:
            return self._connection
        except AttributeError:
            raise AttributeError("Connection not initialized")

    @property
    def transaction(self) -> "AsyncTransaction":
        """Database transaction.

        :return: Database transaction.
        :raises AttributeError: If the transaction is not started.
        """
        try:
            return self._transaction
        except AttributeError:
            raise AttributeError("Transaction not started")

    async def begin_transaction(self) -> None:
        """Open a connection and begin a transaction."""

        self._connection = await self.app.sqlalchemy.open_connection()
        self._transaction = await self.app.sqlalchemy.begin_transaction(self._connection)

    async def end_transaction(self, *, rollback: bool = False) -> None:
        """End a transaction and close the connection.

        :param rollback: If the transaction should be rolled back.
        :raises AttributeError: If the connection is not initialized or the transaction is not started.
        """
        await self.app.sqlalchemy.end_transaction(self.transaction, rollback=rollback)
        del self._transaction

        await self.app.sqlalchemy.close_connection(self.connection)
        del self._connection

    async def begin(self) -> None:
        """Start a unit of work.

        Initialize the connection, begin a transaction, and create the repositories.
        """
        await self.begin_transaction()

        for repository, repository_class in self._repositories.items():
            setattr(self, repository, repository_class(self.connection))

    async def end(self, *, rollback: bool = False) -> None:
        """End a unit of work.

        Close the connection, commit or rollback the transaction, and delete the repositories.

        :param rollback: If the unit of work should be rolled back.
        """
        await self.end_transaction(rollback=rollback)

        for repository in self._repositories.keys():
            delattr(self, repository)

    async def commit(self):
        """Commit the unit of work."""
        await self.connection.commit()

    async def rollback(self):
        """Rollback the unit of work."""
        await self.connection.rollback()
