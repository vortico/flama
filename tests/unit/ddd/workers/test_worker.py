import pytest

from flama.ddd.workers import Worker


class TestCaseWorker:
    @pytest.fixture(scope="function")
    def worker(self, client):
        class FooWorker(Worker): ...

        return FooWorker(client.app)

    def test_init(self, app):
        worker = Worker(app)

        assert worker._app == app

    async def test_async_context_runs_lifecycle(self, app):
        class RecordingWorker(Worker):
            def __init__(self):
                super().__init__(app)
                self.events: list = []

            async def set_up(self) -> None:
                self.events.append("set_up")

            async def tear_down(self, *, rollback: bool = False) -> None:
                self.events.append(("tear_down", rollback))

        worker = RecordingWorker()

        async with worker:
            assert worker.events == ["set_up"]

        assert worker.events == ["set_up", ("tear_down", False)]
