import abc
import inspect
import typing as t

from sqlalchemy.ext.asyncio import AsyncTransaction

from flama.ddd import types
from flama.ddd.repositories import AbstractRepository, SQLAlchemyRepository

if t.TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from flama import Flama


__all__ = ["WorkerType", "AbstractWorker", "SQLAlchemyWorker"]


class WorkerType(abc.ABCMeta):
    def __new__(mcs, name: str, bases: t.Tuple[type], namespace: t.Dict[str, t.Any]):
        namespace["_repositories"] = types.Repositories(
            {
                k: v
                for k, v in namespace.get("__annotations__", {}).items()
                if inspect.isclass(v) and issubclass(v, AbstractRepository)
            }
        )

        return super().__new__(mcs, name, bases, namespace)


class AbstractWorker(abc.ABC):
    _repositories: t.Dict[str, t.Type[AbstractRepository]]

    def __init__(self, app: t.Optional["Flama"] = None):
        self._app = app

    @property
    def app(self) -> "Flama":
        assert self._app, "Worker not initialized"
        return self._app

    @app.setter
    def app(self, app: "Flama"):
        self._app = app

    @app.deleter
    def app(self):
        self._app = None

    @abc.abstractmethod
    async def __aenter__(self) -> "AbstractWorker":
        ...

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        ...

    @abc.abstractmethod
    async def commit(self) -> None:
        ...

    @abc.abstractmethod
    async def rollback(self) -> None:
        ...


class SQLAlchemyWorker(AbstractWorker, metaclass=WorkerType):
    _repositories: t.Dict[str, t.Type[SQLAlchemyRepository]]

    def __init__(self, app: t.Optional["Flama"] = None):
        super().__init__(app)
        self._connection: t.Optional["AsyncConnection"] = None
        self._transaction: t.Optional["AsyncTransaction"] = None

    @property
    def connection(self) -> "AsyncConnection":
        assert self._connection, "Connection not initialized"
        return self._connection

    async def begin(self):
        self._connection = self.app.sqlalchemy.engine.connect()
        await self._connection.__aenter__()
        self._transaction = self._connection.begin()
        await self._transaction

    async def close(self):
        if self._transaction:
            await self._transaction.__aexit__(None, None, None)
            self._transaction = None

        if self._connection:
            await self._connection.__aexit__(None, None, None)
            self._connection = None

    async def __aenter__(self):
        await self.begin()
        for repository, repository_class in self._repositories.items():
            setattr(self, repository, repository_class(self.connection))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

        for repository in self._repositories.keys():
            delattr(self, repository)

    async def commit(self):
        await self.connection.commit()

    async def rollback(self):
        await self.connection.rollback()
