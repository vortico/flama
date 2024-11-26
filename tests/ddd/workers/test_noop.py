import pytest

from flama.ddd.workers import NoopWorker


class TestCaseNoopWorker:
    @pytest.fixture(scope="function")
    def worker(self, client):
        class FooWorker(NoopWorker):
            ...

        return FooWorker(client.app)

    def test_init(self, app):
        worker = NoopWorker(app)

        assert worker._app == app
