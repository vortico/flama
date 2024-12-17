import logging
import typing as t

from flama import exceptions
from flama.ddd.workers.base import BaseWorker

try:
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncTransaction
except Exception:  # pragma: no cover
    raise exceptions.DependencyNotInstalled(
        dependency=exceptions.DependencyNotInstalled.Dependency.sqlalchemy, dependant=__name__
    )


__all__ = ["SQLAlchemyWorker"]

logger = logging.getLogger(__name__)


class SQLAlchemyWorker(BaseWorker):
    """Worker for SQLAlchemy.

    It will provide a connection and a transaction to the database and create the repositories for the entities.
    """

    _connection: AsyncConnection
    _transaction: AsyncTransaction

    @property
    def connection(self) -> AsyncConnection:
        """Connection to the database.

        :return: Connection to the database.
        :raises AttributeError: If the connection is not initialized.
        """
        try:
            return self._connection
        except AttributeError:
            raise AttributeError("Connection not initialized")

    @connection.setter
    def connection(self, connection: AsyncConnection) -> None:
        """Set the connection to the database.

        :param connection: Connection to the database.
        """
        self._connection = connection

    @connection.deleter
    def connection(self) -> None:
        """Delete the connection to the database."""
        del self._connection

    @property
    def transaction(self) -> AsyncTransaction:
        """Database transaction.

        :return: Database transaction.
        :raises AttributeError: If the transaction is not started.
        """
        try:
            return self._transaction
        except AttributeError:
            raise AttributeError("Transaction not started")

    @transaction.setter
    def transaction(self, transaction: AsyncTransaction) -> None:
        """Set the transaction.

        :param transaction: Database transaction.
        """
        self._transaction = transaction

    @transaction.deleter
    def transaction(self) -> None:
        """Delete the transaction."""
        del self._transaction

    async def set_up(self) -> None:
        """Open a connection and begin a transaction."""

        self.connection = await self.app.sqlalchemy.open_connection()
        self.transaction = await self.app.sqlalchemy.begin_transaction(self._connection)

    async def tear_down(self, *, rollback: bool = False) -> None:
        """End a transaction and close the connection.

        :param rollback: If the transaction should be rolled back.
        :raises AttributeError: If the connection is not initialized or the transaction is not started.
        """
        await self.app.sqlalchemy.end_transaction(self.transaction, rollback=rollback)
        del self.transaction

        await self.app.sqlalchemy.close_connection(self.connection)
        del self.connection

    async def repository_params(self) -> tuple[list[t.Any], dict[str, t.Any]]:
        """Get the parameters for initialising the repositories.

        :return: Parameters for initialising the repositories.
        """
        return [self.connection], {}

    async def commit(self):
        """Commit the unit of work."""
        await self.connection.commit()

    async def rollback(self):
        """Rollback the unit of work."""
        await self.connection.rollback()
