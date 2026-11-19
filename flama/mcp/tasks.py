import abc
import asyncio
import dataclasses
import datetime
import enum
import typing as t
import uuid

__all__ = ["TaskStatus", "IdempotencyKey", "Task", "TaskCapacityExceeded", "TaskStore", "InMemoryTaskStore"]


class TaskStatus(enum.StrEnum):
    """Lifecycle states of a task-augmented tool call (SEP-2322)."""

    WORKING = enum.auto()
    INPUT_REQUIRED = enum.auto()
    COMPLETED = enum.auto()
    FAILED = enum.auto()
    CANCELLED = enum.auto()


@dataclasses.dataclass(frozen=True)
class IdempotencyKey:
    """A key a client attaches to a tool call so retrying it returns the task the first call created.

    It is scoped to the caller and the tool, so different callers reusing a key never see each other's tasks.

    :param subject: Subject of the caller.
    :param tool: Name of the tool called.
    :param value: Key the client sent.
    """

    subject: str
    tool: str
    value: str


@dataclasses.dataclass
class Task:
    """A server-directed handle for a long-running tool call (SEP-2322).

    The protocol is stateless, so the handle carries everything needed to drive and resume the call: the originating
    tool ``tool_name``/``arguments`` (to replay the handler), the current ``status``, and, while waiting on the client,
    the pending elicitation ``input_requests`` plus the opaque ``request_state`` the client echoes back. A task created
    for an authenticated principal records its subject as ``owner``, so nobody else can drive it, and the
    ``idempotency_key`` it was created for, if any. It may be discarded once ``ttl_ms`` has elapsed since it was
    created, and is kept indefinitely when ``ttl_ms`` is None.
    """

    id: str
    status: TaskStatus = TaskStatus.WORKING
    tool_name: str | None = None
    arguments: dict[str, t.Any] | None = None
    result: t.Any = None
    error: str | None = None
    ttl_ms: int | None = None
    input_requests: dict[str, t.Any] | None = None
    request_state: str | None = None
    owner: str | None = None
    idempotency_key: IdempotencyKey | None = None
    created_at: datetime.datetime = dataclasses.field(default_factory=lambda: datetime.datetime.now(datetime.UTC))
    updated_at: datetime.datetime = dataclasses.field(default_factory=lambda: datetime.datetime.now(datetime.UTC))
    runner: "asyncio.Task[t.Any] | None" = dataclasses.field(default=None, repr=False, compare=False)

    @property
    def expired(self) -> bool:
        """Whether the task's time to live has elapsed since it was created."""
        return self.ttl_ms is not None and datetime.datetime.now(datetime.UTC) >= self.created_at + datetime.timedelta(
            milliseconds=self.ttl_ms
        )

    def to_dict(self) -> dict[str, t.Any]:
        """Render the task as its wire representation, exposing only the fields relevant to the current status."""
        data: dict[str, t.Any] = {
            "taskId": self.id,
            "status": self.status.value,
            "createdAt": self.created_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "lastUpdatedAt": self.updated_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "ttlMs": self.ttl_ms,
        }

        if self.status == TaskStatus.COMPLETED:
            data["result"] = self.result
        elif self.status == TaskStatus.FAILED:
            data["error"] = self.error
        elif self.status == TaskStatus.INPUT_REQUIRED:
            data["inputRequests"] = self.input_requests
            data["requestState"] = self.request_state

        return data


class TaskCapacityExceeded(Exception):
    """A task store holds as many tasks as it may, none of which has finished, so no other task can be created."""


class TaskStore(abc.ABC):
    """Persistence boundary for task state.

    Execution stays in-process (the running coroutine lives on :attr:`Task.runner`), but the task *records* go through
    this store so a deployment can back them onto shared storage and let any instance answer ``tasks/get`` and friends.
    """

    @abc.abstractmethod
    async def create(
        self,
        *,
        ttl_ms: int | None = None,
        tool_name: str | None = None,
        arguments: dict[str, t.Any] | None = None,
        idempotency_key: IdempotencyKey | None = None,
    ) -> tuple[Task, bool]:
        """Create and persist a new task in the ``working`` state, unless one was already created for
        ``idempotency_key``.

        Looking the key up and creating the task is one atomic operation, so concurrent calls with the same key create
        a single task, whether they reach one instance or several sharing the store.

        :param ttl_ms: Time the task may be kept for after it is created, indefinitely if None.
        :param tool_name: Tool the task runs.
        :param arguments: Arguments the tool is called with.
        :param idempotency_key: Idempotency key the task is created for, if any.
        :return: The task, and whether it was created rather than found for ``idempotency_key``.
        :raises TaskCapacityExceeded: If no other task can be created.
        """
        ...

    @abc.abstractmethod
    async def get(self, task_id: str) -> Task | None:
        """Return the task with ``task_id``, or ``None`` if it is unknown or has expired."""
        ...

    @abc.abstractmethod
    async def save(self, task: Task) -> None:
        """Persist the current state of ``task``, recording when it was last updated."""
        ...

    @abc.abstractmethod
    async def delete(self, task_id: str) -> None:
        """Remove the task with ``task_id``, and the key it was created for, if present."""
        ...


class InMemoryTaskStore(TaskStore):
    """Default in-process :class:`TaskStore` backed by a dictionary.

    Expired tasks are discarded as the store is used, and once it holds ``max_tasks`` the oldest finished task makes
    room for a new one, so the store does not grow without bound even when tasks never expire.

    :param max_tasks: Most tasks the store holds.
    """

    def __init__(self, *, max_tasks: int = 1000) -> None:
        self.max_tasks = max_tasks
        self._tasks: dict[str, Task] = {}
        self._idempotency_keys: dict[IdempotencyKey, str] = {}

    async def create(
        self,
        *,
        ttl_ms: int | None = None,
        tool_name: str | None = None,
        arguments: dict[str, t.Any] | None = None,
        idempotency_key: IdempotencyKey | None = None,
    ) -> tuple[Task, bool]:
        self._discard_expired()

        if idempotency_key is not None and (task_id := self._idempotency_keys.get(idempotency_key)) is not None:
            return self._tasks[task_id], False

        if len(self._tasks) >= self.max_tasks:
            finished = (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            if (oldest := next((x for x in self._tasks.values() if x.status in finished), None)) is None:
                raise TaskCapacityExceeded(f"The store already holds {self.max_tasks} unfinished tasks")

            self._remove(oldest.id)

        task = Task(
            id=uuid.uuid4().hex,
            tool_name=tool_name,
            arguments=arguments,
            ttl_ms=ttl_ms,
            idempotency_key=idempotency_key,
        )
        self._tasks[task.id] = task
        if idempotency_key is not None:
            self._idempotency_keys[idempotency_key] = task.id

        return task, True

    async def get(self, task_id: str) -> Task | None:
        self._discard_expired()
        return self._tasks.get(task_id)

    async def save(self, task: Task) -> None:
        task.updated_at = datetime.datetime.now(datetime.UTC)
        self._tasks[task.id] = task

    async def delete(self, task_id: str) -> None:
        self._remove(task_id)

    def _discard_expired(self) -> None:
        """Discard the tasks whose time to live has elapsed."""
        for task_id in [x.id for x in self._tasks.values() if x.expired]:
            self._remove(task_id)

    def _remove(self, task_id: str) -> None:
        """Remove a task, along with the key it was created for."""
        if (task := self._tasks.pop(task_id, None)) is not None and task.idempotency_key is not None:
            self._idempotency_keys.pop(task.idempotency_key, None)
