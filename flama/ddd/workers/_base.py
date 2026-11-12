import abc
import asyncio
import contextlib
import contextvars
import dataclasses
import enum
import logging
import typing as t

from flama import _compat, types
from flama.ddd.exceptions import UnitOfWorkError
from flama.ddd.repositories import BaseRepository
from flama.exceptions import ApplicationError

logger = logging.getLogger(__name__)

__all__ = ["AbstractWorker", "BaseWorker"]


class Repositories(dict[str, t.Callable[..., BaseRepository]]): ...


class _UnitOfWorkStatus(enum.Enum):
    open = enum.auto()
    # A block joined to the unit of work failed or rolled back, so it rolls back when its outermost block ends.
    doomed = enum.auto()
    closed = enum.auto()


@dataclasses.dataclass
class _UnitOfWork:
    """A unit of work a request holds on a worker, shared by every block joined to it."""

    owner: "asyncio.Task[t.Any] | None"
    depth: int = 1
    status: _UnitOfWorkStatus = _UnitOfWorkStatus.open


class _UnitsOfWork:
    """The units of work opened on a worker, one for each request, and the lock serialising them.

    Each request runs in a task of its own, whose context holds the unit of work it opened. A unit of work opened while
    the request already holds one joins it, and only its outermost block ends it.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._context: contextvars.ContextVar[_UnitOfWork | None] = contextvars.ContextVar("unit_of_work", default=None)

    @property
    def is_open(self) -> bool:
        """Whether the current request has a unit of work open.

        :return: True if a unit of work is open.
        """
        return (unit := self._context.get()) is not None and unit.status is not _UnitOfWorkStatus.closed

    @property
    def joined(self) -> bool:
        """Whether the current task is in a block joined to the unit of work, rather than in its outermost one.

        :return: True if in a joined block.
        """
        return (unit := self._owned()) is not None and unit.depth > 1

    def doom(self) -> None:
        """Mark the unit of work to roll back when its outermost block ends.

        Called when a block joined to it fails or rolls back, since the block cannot undo its own part alone.

        :raises UnitOfWorkError: If no unit of work is open.
        """
        if (unit := self._owned()) is None:
            raise UnitOfWorkError("No unit of work is open on this worker")

        unit.status = _UnitOfWorkStatus.doomed

    async def enter(self, *, join: bool, begin: t.Callable[[], t.Awaitable[None]]) -> None:
        """Open a unit of work, or join the one the current request already holds.

        :param join: Whether to join a unit of work already open, rather than refuse to run inside one.
        :param begin: Start of the unit of work, run when it is opened rather than joined.
        :raises UnitOfWorkError: If told not to join one already open, or entered from a task running concurrently
            with the one holding it.
        """
        if (unit := self._owned()) is not None:
            if not join:
                raise UnitOfWorkError("A unit of work is already open on this worker")

            unit.depth += 1
            return

        await self._lock.acquire()
        try:
            logger.debug("Start unit of work")
            await begin()
        except BaseException:
            self._lock.release()
            raise

        self._context.set(_UnitOfWork(owner=asyncio.current_task()))

    async def exit(self, *, failed: bool, end: t.Callable[..., t.Awaitable[None]]) -> None:
        """Leave the unit of work, ending it from its outermost block.

        :param failed: Whether the block is left by an exception.
        :param end: End of the unit of work, run from its outermost block with whether to roll it back.
        :raises UnitOfWorkError: If no unit of work is open, or the outermost block is left normally after a block
            joined to it failed or rolled back.
        """
        if (unit := self._owned()) is None:
            raise UnitOfWorkError("No unit of work is open on this worker")

        if unit.depth > 1:
            if failed:
                self.doom()
            unit.depth -= 1
            return

        doomed = unit.status is _UnitOfWorkStatus.doomed
        try:
            await end(rollback=failed or doomed)
            logger.debug("End unit of work")
        finally:
            unit.status = _UnitOfWorkStatus.closed
            self._context.set(None)
            self._lock.release()

        if doomed and not failed:
            raise UnitOfWorkError("The unit of work was rolled back, as a block joined to it failed or rolled back")

    def _owned(self) -> _UnitOfWork | None:
        """The unit of work the current request holds, provided the current task is the one holding it.

        :return: The unit of work, or None when none is open.
        :raises UnitOfWorkError: If it is held by another task, whose connection cannot be shared concurrently.
        """
        if (unit := self._context.get()) is None or unit.status is _UnitOfWorkStatus.closed:
            return None

        if unit.owner is not asyncio.current_task():
            raise UnitOfWorkError("A unit of work cannot be used from a task running concurrently with its holder")

        return unit


class AbstractWorker(abc.ABC):
    """Abstract class for workers.

    It will be used to define the workers for the application. A worker must provide a mechanism to isolate a single
    unit of work that will be used to interact with the repositories and entities of the application.

    A unit of work opened while the current request already holds one on the worker joins it, and only the outermost
    block ends it: it commits, or rolls back when it fails or a block joined to it fails or rolls back.
    """

    def __init__(self, app: types.App | None = None):
        """Initialize the worker.

        It will receive the application instance as a parameter.

        :param app: Application instance.
        """
        self._app = app
        self._units_of_work = _UnitsOfWork()

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

    @property
    def is_open(self) -> bool:
        """Whether the current request has a unit of work open on this worker.

        :return: True if a unit of work is open.
        """
        return self._units_of_work.is_open

    @contextlib.asynccontextmanager
    async def open(self, *, join: bool = True) -> t.AsyncIterator[t.Self]:
        """Open a unit of work, or join the one the current request already holds on this worker.

        Entering the worker directly is opening it with the defaults.

        :param join: Whether to join a unit of work already open, rather than refuse to run inside one.
        :raises UnitOfWorkError: If told not to join one already open, or entered from a task running concurrently
            with the one holding it.
        """
        await self._units_of_work.enter(join=join, begin=self.begin)
        try:
            yield self
        except BaseException:
            await self._units_of_work.exit(failed=True, end=self.end)
            raise
        await self._units_of_work.exit(failed=False, end=self.end)

    async def __aenter__(self) -> t.Self:
        """Open a unit of work, or join the one the current request already holds on this worker."""
        await self._units_of_work.enter(join=True, begin=self.begin)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Leave the unit of work, ending it from its outermost block."""
        await self._units_of_work.exit(failed=exc_type is not None, end=self.end)

    async def commit(self) -> None:
        """Commit the unit of work.

        :raises UnitOfWorkError: If called from a block joined to the unit of work, since only its outermost block
            commits it.
        """
        if self._units_of_work.joined:
            raise UnitOfWorkError("Only the outermost block of a unit of work commits it")

        await self._commit()

    async def rollback(self) -> None:
        """Roll back the unit of work.

        Called from a block joined to it, the unit of work is marked to roll back when its outermost block ends.
        """
        if self._units_of_work.joined:
            self._units_of_work.doom()
            return

        await self._rollback()

    @abc.abstractmethod
    async def _commit(self) -> None:
        """Commit the work done so far in the unit of work."""
        ...

    @abc.abstractmethod
    async def _rollback(self) -> None:
        """Roll back the work done so far in the unit of work."""
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
