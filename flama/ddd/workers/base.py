import abc
import asyncio
import inspect
import logging
import typing as t

from flama.ddd.repositories import AbstractRepository
from flama.exceptions import ApplicationError

if t.TYPE_CHECKING:
    from flama import Flama

logger = logging.getLogger(__name__)

Repositories = t.NewType("Repositories", t.Dict[str, t.Type[AbstractRepository]])

__all__ = ["WorkerType", "AbstractWorker"]


class WorkerType(abc.ABCMeta):
    """Metaclass for workers.

    It will gather all the repositories defined in the class as class attributes as a single dictionary under the name
    `_repositories`.
    """

    def __new__(mcs, name: str, bases: t.Tuple[type], namespace: t.Dict[str, t.Any]):
        if not mcs._is_abstract(namespace) and "__annotations__" in namespace:
            namespace["_repositories"] = Repositories(
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
        self._lock = asyncio.Lock()

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
        await self._lock.acquire()
        logger.debug("Start unit of work")
        await self.begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End a unit of work."""
        await self.end(rollback=exc_type is not None)
        logger.debug("End unit of work")
        self._lock.release()

    @abc.abstractmethod
    async def commit(self) -> None:
        """Commit the unit of work."""
        ...

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Rollback the unit of work."""
        ...
