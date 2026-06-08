import pytest

from flama.mcp.tasks import InMemoryTaskStore, Task, TaskStatus


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
                {"taskId": "t2", "status": "completed", "ttlMs": 0, "result": {"content": []}},
                id="completed",
            ),
            pytest.param(
                Task(id="t3", status=TaskStatus.FAILED, error="boom"),
                {"taskId": "t3", "status": "failed", "ttlMs": 0, "error": "boom"},
                id="failed",
            ),
            pytest.param(
                Task(id="t4", status=TaskStatus.CANCELLED),
                {"taskId": "t4", "status": "cancelled", "ttlMs": 0},
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
                    "ttlMs": 0,
                    "inputRequests": {"confirm": {"type": "elicitation"}},
                    "requestState": "state",
                },
                id="input_required",
            ),
        ),
    )
    def test_to_dict(self, task, expected):
        assert task.to_dict() == expected


class TestCaseInMemoryTaskStore:
    @pytest.fixture(scope="function")
    def store(self):
        return InMemoryTaskStore()

    async def test_create(self, store):
        task = await store.create(ttl_ms=10, tool_name="add", arguments={"a": 1})

        assert task.id
        assert task.status == TaskStatus.WORKING
        assert task.ttl_ms == 10
        assert task.tool_name == "add"
        assert task.arguments == {"a": 1}
        assert await store.get(task.id) is task

    async def test_create_unique_ids(self, store):
        first = await store.create()
        second = await store.create()

        assert first.id != second.id

    async def test_get_missing(self, store):
        assert await store.get("unknown") is None

    async def test_save(self, store):
        task = await store.create()
        task.status = TaskStatus.COMPLETED
        await store.save(task)

        assert (await store.get(task.id)).status == TaskStatus.COMPLETED

    async def test_delete(self, store):
        task = await store.create()
        await store.delete(task.id)

        assert await store.get(task.id) is None

    async def test_delete_missing(self, store):
        await store.delete("unknown")
