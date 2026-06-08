import abc
import asyncio
import dataclasses
import enum
import typing as t
import uuid

from flama import compat

__all__ = ["TaskStatus", "Task", "TaskStore", "InMemoryTaskStore"]


class TaskStatus(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
    """Lifecycle states of a task-augmented tool call (SEP-2322)."""

    WORKING = enum.auto()
    INPUT_REQUIRED = enum.auto()
    COMPLETED = enum.auto()
    FAILED = enum.auto()
    CANCELLED = enum.auto()


@dataclasses.dataclass
class Task:
    """A server-directed handle for a long-running tool call (SEP-2322).

    The protocol is stateless, so the handle carries everything needed to drive and resume the call: the originating
    tool ``tool_name``/``arguments`` (to replay the handler), the current ``status``, and, while waiting on the client,
    the pending elicitation ``input_requests`` plus the opaque ``request_state`` the client echoes back.
    """

    id: str
    status: TaskStatus = TaskStatus.WORKING
    tool_name: str | None = None
    arguments: dict[str, t.Any] | None = None
    result: t.Any = None
    error: str | None = None
    ttl_ms: int = 0
    input_requests: dict[str, t.Any] | None = None
    request_state: str | None = None
    runner: "asyncio.Task[t.Any] | None" = dataclasses.field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, t.Any]:
        """Render the task as its wire representation, exposing only the fields relevant to the current status."""
        data: dict[str, t.Any] = {"taskId": self.id, "status": self.status.value, "ttlMs": self.ttl_ms}

        if self.status == TaskStatus.COMPLETED:
            data["result"] = self.result
        elif self.status == TaskStatus.FAILED:
            data["error"] = self.error
        elif self.status == TaskStatus.INPUT_REQUIRED:
            data["inputRequests"] = self.input_requests
            data["requestState"] = self.request_state

        return data


class TaskStore(abc.ABC):
    """Persistence boundary for task state.

    Execution stays in-process (the running coroutine lives on :attr:`Task.runner`), but the task *records* go through
    this store so a deployment can back them onto shared storage and let any instance answer ``tasks/get`` and friends.
    """

    @abc.abstractmethod
    async def create(
        self, *, ttl_ms: int = 0, tool_name: str | None = None, arguments: dict[str, t.Any] | None = None
    ) -> Task:
        """Create and persist a new task in the ``working`` state, returning it with a freshly minted id."""
        ...

    @abc.abstractmethod
    async def get(self, task_id: str) -> Task | None:
        """Return the task with ``task_id``, or ``None`` if it is unknown."""
        ...

    @abc.abstractmethod
    async def save(self, task: Task) -> None:
        """Persist the current state of ``task``."""
        ...

    @abc.abstractmethod
    async def delete(self, task_id: str) -> None:
        """Remove the task with ``task_id`` if present."""
        ...


class InMemoryTaskStore(TaskStore):
    """Default in-process :class:`TaskStore` backed by a dictionary."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    async def create(
        self, *, ttl_ms: int = 0, tool_name: str | None = None, arguments: dict[str, t.Any] | None = None
    ) -> Task:
        task = Task(id=uuid.uuid4().hex, tool_name=tool_name, arguments=arguments, ttl_ms=ttl_ms)
        self._tasks[task.id] = task
        return task

    async def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    async def save(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def delete(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)
