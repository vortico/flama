from unittest.mock import MagicMock, call, patch

import pytest

from flama.ddd.repositories import HTTPRepository
from flama.ddd.workers import HTTPWorker


class TestCaseHTTPWorker:
    @pytest.fixture(scope="function")
    def worker(self, client):
        class FooWorker(HTTPWorker):
            bar: HTTPRepository

        return FooWorker(client.app)

    def test_init(self, app):
        worker = HTTPWorker(app)

        assert worker._app == app
        assert not hasattr(worker, "_client")

    def test_client(self, worker):
        with pytest.raises(AttributeError, match="Client not initialized"):
            worker.client

    def test_url(self, worker):
        with pytest.raises(AttributeError, match="URL not initialized"):
            worker.url

    async def test_begin_transaction(self, worker):
        worker._url = "foo"
        worker._client = MagicMock()

        await worker.begin_transaction()
        assert worker._client.__aenter__.await_args_list == [call()]

    async def test_end_transaction(self, worker):
        worker._url = "foo"
        worker._client = MagicMock()

        await worker.end_transaction()
        assert worker._client.__aexit__.await_args_list == [call()]

    async def test_begin(self, worker):
        worker._url = "foo"

        with patch.object(worker, "begin_transaction"), patch("flama.client.Client"):
            assert not hasattr(worker, "bar")
            assert not hasattr(worker, "_client")

            await worker.begin()

            assert hasattr(worker, "_client")
            assert worker.begin_transaction.await_args_list == [call()]
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
        worker._client = MagicMock()

        with patch.object(worker, "end_transaction"):
            assert hasattr(worker, "bar")
            assert hasattr(worker, "_client")

            await worker.end(rollback=rollback)

            assert worker.end_transaction.await_args_list == [call()]
            assert not hasattr(worker, "bar")
            assert not hasattr(worker, "_client")
