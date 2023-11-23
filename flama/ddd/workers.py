import abc
import inspect
import typing as t

from sqlalchemy.ext.asyncio import AsyncTransaction

from flama.ddd import types
from flama.ddd.repositories import AbstractRepository, SQLAlchemyRepository
from flama.exceptions import ApplicationError

if t.TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from flama import Flama


__all__ = ["WorkerType", "AbstractWorker", "SQLAlchemyWorker"]


class WorkerType(abc.ABCMeta):
    """Metaclass for workers.

    It will gather all the repositories defined in the class as class attributes as a single dictionary under the name
    `_repositories`.
    """

    def __new__(mcs, name: str, bases: t.Tuple[type], namespace: t.Dict[str, t.Any]):
        if not mcs._is_abstract(namespace) and "__annotations__" in namespace:
            namespace["_repositories"] = types.Repositories(
                {
                    k: v
                    for k, v in namespace["__annotations__"].items()
                    if inspect.isclass(v) and issubclass(v, AbstractRepository)
                }
            )

            namespace["__annotations__"] = {
                k: v for k, v in namespace["__annotations__"].items() if k not in namespace["_repositories"]
            }

        return super().__new__(mcs, name, bases, namespace)

    @staticmethod
    def _is_abstract(namespace: t.Dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.ddd.workers" and namespace.get("__qualname__") == "AbstractWorker"


class AbstractWorker(abc.ABC, metaclass=WorkerType):
    """Abstract class for workers.

    It will be used to define the workers for the application. A worker consists of a set of repositories that will be
    used to interact with entities and a mechanism for isolate a single unit of work.
    """

    _repositories: t.ClassVar[t.Dict[str, t.Type[AbstractRepository]]]

    def __init__(self, app: t.Optional["Flama"] = None):
        """Initialize the worker.

        It will receive the application instance as a parameter.

        :param app: Application instance.
        """
        self._app = app

    @property
    def app(self) -> "Flama":
        """Application instance.

        :return: Application instance.
        """
        if not self._app:
            raise ApplicationError("Worker not initialized")

        return self._app

    @app.setter
    def app(self, app: "Flama") -> None:
        """Set the application instance.

        :param app: Application instance.
        """
        self._app = app

    @app.deleter
    def app(self) -> None:
        """Delete the application instance."""
        self._app = None

    @abc.abstractmethod
    async def begin(self) -> None:
        """Start a unit of work."""
        ...

    @abc.abstractmethod
    async def end(self, *, rollback: bool = False) -> None:
        """End a unit of work.

        :param rollback: If the unit of work should be rolled back.
        """
        ...

    async def __aenter__(self) -> "AbstractWorker":
        """Start a unit of work."""
        await self.begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End a unit of work."""
        await self.end(rollback=exc_type is not None)

    @abc.abstractmethod
    async def commit(self) -> None:
        """Commit the unit of work."""
        ...

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Rollback the unit of work."""
        ...


class SQLAlchemyWorker(AbstractWorker):
    _repositories: t.ClassVar[t.Dict[str, t.Type[SQLAlchemyRepository]]]
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
