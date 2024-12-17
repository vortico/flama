from unittest.mock import MagicMock, call, patch

import pytest

from flama.ddd.repositories import HTTPRepository
from flama.ddd.workers import HTTPWorker


class TestCaseHTTPWorker:
    @pytest.fixture(scope="function")
    def worker(self, client):
        class FooWorker(HTTPWorker):
            bar: HTTPRepository

        return FooWorker("foo", client.app)

    def test_init(self, app):
        worker = HTTPWorker("foo", app)

        assert worker._app == app
        assert worker._url == "foo"
        assert not hasattr(worker, "client")

    def test_client(self, worker):
        with pytest.raises(AttributeError, match="Client not initialized"):
            worker.client

    async def test_set_up(self, worker):
        with patch("flama.client.Client"):
            await worker.set_up()
            assert worker.client.__aenter__.await_args_list == [call()]

    async def test_tear_down(self, worker):
        client_mock = MagicMock()
        worker.client = client_mock

        await worker.tear_down()
        assert client_mock.__aexit__.await_args_list == [call()]

    async def test_begin(self, worker):
        worker.client = MagicMock()

        with patch.object(worker, "set_up"):
            assert not hasattr(worker, "bar")

            await worker.begin()

            assert worker.set_up.await_args_list == [call()]
            assert hasattr(worker, "bar")
            assert isinstance(worker.bar, HTTPRepository)

    @pytest.mark.parametrize(
        ["rollback"],
        (
            pytest.param(True, id="ok_rollback"),
            pytest.param(False, id="ok_commit"),
        ),
    )
    async def test_end(self, worker, rollback):
        worker.bar = MagicMock()
        worker.client = MagicMock()

        with patch.object(worker, "tear_down"):
            assert hasattr(worker, "bar")

            await worker.end(rollback=rollback)

            assert worker.tear_down.await_args_list == [call(rollback=rollback)]
            assert not hasattr(worker, "bar")
