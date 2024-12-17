import abc
import asyncio
import logging
import typing as t

from flama.ddd.repositories import BaseRepository
from flama.exceptions import ApplicationError

if t.TYPE_CHECKING:
    from flama import Flama

logger = logging.getLogger(__name__)

__all__ = ["AbstractWorker", "BaseWorker"]


Repositories = t.NewType("Repositories", dict[str, type[BaseRepository]])


class AbstractWorker(abc.ABC):
    """Abstract class for workers.

    It will be used to define the workers for the application. A worker must provide a mechanism to isolate a single
    unit of work that will be used to interact with the repositories and entities of the application.
    """

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


class WorkerType(abc.ABCMeta):
    """Metaclass for workers.

    It will gather all the repositories defined in the class as class attributes as a single dictionary under the name
    `_repositories` and remove them from the class annotations.
    """

    def __new__(mcs, name: str, bases: tuple[type], namespace: dict[str, t.Any]):
        if not mcs._is_base(namespace) and "__annotations__" in namespace:
            namespace["_repositories"] = Repositories(
                {k: v for k, v in namespace["__annotations__"].items() if mcs._is_repository(v)}
            )

            namespace["__annotations__"] = {
                k: v for k, v in namespace["__annotations__"].items() if k not in namespace["_repositories"]
            }

        return super().__new__(mcs, name, bases, namespace)

    @staticmethod
    def _is_base(namespace: dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.ddd.workers" and namespace.get("__qualname__") == "BaseWorker"

    @staticmethod
    def _is_repository(obj: t.Any) -> bool:
        try:
            return issubclass(obj, BaseRepository)
        except TypeError:
            return False


class BaseWorker(AbstractWorker, metaclass=WorkerType):
    """Base class for workers.

    It will be used to define the workers for the application. A worker consists of a set of repositories that will be
    used to interact with entities and a mechanism for isolate a single unit of work.

    It will gather all the repositories defined in the class as class attributes as a single dictionary under the name
    `_repositories` and remove them from the class annotations.
    """

    _repositories: t.ClassVar[dict[str, type[BaseRepository]]]

    @abc.abstractmethod
    async def set_up(self) -> None:
        """First step in starting a unit of work."""
        ...

    @abc.abstractmethod
    async def tear_down(self, *, rollback: bool = False) -> None:
        """Last step in ending a unit of work.

        :param rollback: If the unit of work should be rolled back.
        """
        ...

    @abc.abstractmethod
    async def repository_params(self) -> tuple[list[t.Any], dict[str, t.Any]]:
        """Get the parameters for initialising the repositories.

        :return: Parameters for initialising the repositories.
        """
        ...

    async def begin(self) -> None:
        """Start a unit of work."""
        await self.set_up()

        args, kwargs = await self.repository_params()

        for repository, repository_class in self._repositories.items():
            setattr(self, repository, repository_class(*args, **kwargs))

    async def end(self, *, rollback: bool = False) -> None:
        """End a unit of work.

        :param rollback: If the unit of work should be rolled back.
        """
        await self.tear_down(rollback=rollback)

        for repository in self._repositories.keys():
            delattr(self, repository)
