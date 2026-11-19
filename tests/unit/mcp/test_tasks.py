import datetime

import pytest

from flama.mcp.tasks import IdempotencyKey, InMemoryTaskStore, Task, TaskCapacityExceeded, TaskStatus

CREATED_AT = datetime.datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=datetime.UTC)
UPDATED_AT = datetime.datetime(2026, 1, 1, 12, 0, 5, tzinfo=datetime.UTC)
TIMESTAMPS = {"createdAt": "2026-01-01T12:00:00.123Z", "lastUpdatedAt": "2026-01-01T12:00:05.000Z"}


class TestCaseTask:
    @pytest.mark.parametrize(
        ["task", "expected"],
        (
            pytest.param(
                Task(id="t1", status=TaskStatus.WORKING, ttl_ms=5),
                {"taskId": "t1", "status": "working", "ttlMs": 5},
                id="working",
            ),
            pytest.param(
                Task(id="t2", status=TaskStatus.COMPLETED, result={"content": []}),
                {"taskId": "t2", "status": "completed", "ttlMs": None, "result": {"content": []}},
                id="completed",
            ),
            pytest.param(
                Task(id="t3", status=TaskStatus.FAILED, error="boom"),
                {"taskId": "t3", "status": "failed", "ttlMs": None, "error": "boom"},
                id="failed",
            ),
            pytest.param(
                Task(id="t4", status=TaskStatus.CANCELLED),
                {"taskId": "t4", "status": "cancelled", "ttlMs": None},
                id="cancelled",
            ),
            pytest.param(
                Task(
                    id="t5",
                    status=TaskStatus.INPUT_REQUIRED,
                    input_requests={"confirm": {"type": "elicitation"}},
                    request_state="state",
                ),
                {
                    "taskId": "t5",
                    "status": "input_required",
                    "ttlMs": None,
                    "inputRequests": {"confirm": {"type": "elicitation"}},
                    "requestState": "state",
                },
                id="input_required",
            ),
        ),
    )
    def test_to_dict(self, task, expected):
        task.created_at = CREATED_AT
        task.updated_at = UPDATED_AT

        assert task.to_dict() == {**expected, **TIMESTAMPS}

    @pytest.mark.parametrize(
        ["ttl_ms", "age_ms", "expired"],
        (
            pytest.param(None, 10**9, False, id="unlimited"),
            pytest.param(1000, 10, False, id="alive"),
            pytest.param(1000, 2000, True, id="expired"),
        ),
    )
    def test_expired(self, ttl_ms, age_ms, expired):
        task = Task(id="t1", ttl_ms=ttl_ms)
        task.created_at -= datetime.timedelta(milliseconds=age_ms)

        assert task.expired is expired


class TestCaseInMemoryTaskStore:
    @pytest.fixture(scope="function")
    def store(self):
        return InMemoryTaskStore()

    @pytest.fixture(scope="function")
    def idempotency_key(self):
        return IdempotencyKey(subject="alice", tool="add", value="k1")

    async def test_create(self, store):
        task, created = await store.create(ttl_ms=10, tool_name="add", arguments={"a": 1})

        assert created
        assert task.id
        assert task.status == TaskStatus.WORKING
        assert task.ttl_ms == 10
        assert task.tool_name == "add"
        assert task.arguments == {"a": 1}
        assert task.idempotency_key is None
        assert await store.get(task.id) is task

    async def test_create_unique_ids(self, store):
        first, _ = await store.create()
        second, _ = await store.create()

        assert first.id != second.id

    async def test_create_same_key(self, store, idempotency_key):
        first, first_created = await store.create(tool_name="add", idempotency_key=idempotency_key)
        second, second_created = await store.create(tool_name="add", idempotency_key=idempotency_key)

        assert first_created
        assert not second_created
        assert second is first
        assert first.idempotency_key == idempotency_key

    @pytest.mark.parametrize(
        "other",
        (
            pytest.param(IdempotencyKey(subject="bob", tool="add", value="k1"), id="other_subject"),
            pytest.param(IdempotencyKey(subject="alice", tool="sub", value="k1"), id="other_tool"),
            pytest.param(IdempotencyKey(subject="alice", tool="add", value="k2"), id="other_key"),
        ),
    )
    async def test_create_other_key(self, store, idempotency_key, other):
        first, _ = await store.create(idempotency_key=idempotency_key)
        second, created = await store.create(idempotency_key=other)

        assert created
        assert second is not first

    async def test_create_expired_key(self, store, idempotency_key):
        first, _ = await store.create(ttl_ms=1000, idempotency_key=idempotency_key)
        first.created_at -= datetime.timedelta(seconds=2)

        second, created = await store.create(ttl_ms=1000, idempotency_key=idempotency_key)

        assert created
        assert second is not first
        assert await store.get(first.id) is None

    async def test_create_evicts_oldest_finished(self):
        store = InMemoryTaskStore(max_tasks=2)
        first, _ = await store.create()
        second, _ = await store.create()
        first.status = second.status = TaskStatus.COMPLETED

        third, created = await store.create()

        assert created
        assert await store.get(first.id) is None
        assert await store.get(second.id) is second
        assert await store.get(third.id) is third

    async def test_create_full(self):
        store = InMemoryTaskStore(max_tasks=1)
        await store.create()

        with pytest.raises(TaskCapacityExceeded):
            await store.create()

    async def test_get_missing(self, store):
        assert await store.get("unknown") is None

    async def test_get_expired(self, store):
        task, _ = await store.create(ttl_ms=1000)
        task.created_at -= datetime.timedelta(seconds=2)

        assert await store.get(task.id) is None

    async def test_save(self, store):
        task, _ = await store.create()
        updated_at = task.updated_at
        task.status = TaskStatus.COMPLETED
        await store.save(task)

        saved = await store.get(task.id)
        assert saved.status == TaskStatus.COMPLETED
        assert saved.updated_at >= updated_at

    async def test_delete(self, store, idempotency_key):
        task, _ = await store.create(idempotency_key=idempotency_key)
        await store.delete(task.id)

        assert await store.get(task.id) is None
        assert (await store.create(idempotency_key=idempotency_key))[1]

    async def test_delete_missing(self, store):
        await store.delete("unknown")
