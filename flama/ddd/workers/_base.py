import abc
import asyncio
import logging
import typing as t

from flama import _compat, types
from flama.ddd.repositories import BaseRepository
from flama.exceptions import ApplicationError

logger = logging.getLogger(__name__)

__all__ = ["AbstractWorker", "BaseWorker"]


class Repositories(dict[str, t.Callable[..., BaseRepository]]): ...


class AbstractWorker(abc.ABC):
    """Abstract class for workers.

    It will be used to define the workers for the application. A worker must provide a mechanism to isolate a single
    unit of work that will be used to interact with the repositories and entities of the application.
    """

    def __init__(self, app: types.App | None = None):
        """Initialize the worker.

        It will receive the application instance as a parameter.

        :param app: Application instance.
        """
        self._app = app
        self._lock = asyncio.Lock()

    @property
    def app(self) -> types.App:
        """Application instance.

        :return: Application instance.
        """
        if not self._app:
            raise ApplicationError("Worker not initialized")

        return self._app

    @app.setter
    def app(self, app: types.App) -> None:
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

    It will gather all the repositories defined in the class as class attributes, along with the ones inherited from
    its bases, as a single dictionary under the name `_repositories` and remove them from the class annotations.
    """

    _repositories: Repositories

    def __new__(mcs, name: str, bases: tuple[type], namespace: dict[str, t.Any]):
        cls = super().__new__(mcs, name, bases, namespace)

        if mcs._is_base(namespace):
            return cls

        try:
            annotations = {
                k: mcs._resolve(v, cls)
                # PORT: Replace compat when stop supporting 3.13
                for k, v in _compat.get_annotations(cls, format=_compat.Format.FORWARDREF).items()
            }
        except Exception:
            annotations = {}

        inherited = {
            k: v
            for base in reversed(bases)
            for k, v in getattr(base, "_repositories", {}).items()
            if k not in annotations
        }
        cls._repositories = Repositories(
            {**inherited, **{k: v for k, v in annotations.items() if mcs._is_repository(v)}}
        )
        cls.__annotations__ = {k: v for k, v in annotations.items() if k not in cls._repositories}

        return cls

    @staticmethod
    def _is_base(namespace: dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.ddd.workers" and namespace.get("__qualname__") == "BaseWorker"

    @staticmethod
    def _resolve(annotation: t.Any, owner: type) -> t.Any:
        if not isinstance(annotation, str | t.ForwardRef):
            return annotation

        try:
            # PORT: Replace compat when stop supporting 3.13
            return _compat.evaluate_forward_ref(
                t.ForwardRef(annotation) if isinstance(annotation, str) else annotation, owner=owner
            )
        except Exception:
            return annotation

    @staticmethod
    def _is_repository(annotation: t.Any) -> bool:
        annotation = types.Annotation(annotation)
        return (
            not annotation.optional
            and isinstance(annotation.origin, type)
            and issubclass(annotation.origin, BaseRepository)
        )


class BaseWorker(AbstractWorker, metaclass=WorkerType):
    """Base class for workers.

    It will be used to define the workers for the application. A worker consists of a set of repositories that will be
    used to interact with entities and a mechanism for isolate a single unit of work.

    It will gather all the repositories defined in the class as class attributes as a single dictionary under the name
    `_repositories` and remove them from the class annotations.
    """

    _repositories: t.ClassVar[Repositories]

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
