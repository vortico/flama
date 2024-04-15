from unittest.mock import AsyncMock, call, patch

import pytest

from flama.exceptions import ApplicationError


class TestCaseAbstractWorker:
    def test_new(self, worker):
        assert hasattr(worker, "_repositories")

    def test_app(self, app, worker):
        with pytest.raises(ApplicationError, match="Worker not initialized"):
            worker.app

        worker.app = app

        assert worker.app == app

        del worker.app

        with pytest.raises(ApplicationError, match="Worker not initialized"):
            worker.app

    async def test_async_context(self, app, worker):
        worker.app = app

        with patch.multiple(worker, begin=AsyncMock(), end=AsyncMock()):
            async with worker:
                assert worker.begin.await_args_list == [call()]
                assert worker.end.await_args_list == []

            assert worker.begin.await_args_list == [call()]
            assert worker.end.await_args_list == [call(rollback=False)]
