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
