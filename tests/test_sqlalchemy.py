import sys
from unittest.mock import Mock, call, patch

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.testclient import TestClient

from flama import Flama
from flama.sqlalchemy import SQLAlchemyModule

if sys.version_info >= (3, 8):  # PORT: Remove when Python3.7 EOL
    from unittest.mock import AsyncMock


class TestCaseSQLAlchemyModule:
    @pytest.fixture
    def app(self):
        app = Flama(sqlalchemy_database="sqlite+aiosqlite://")
        with TestClient(app):  # Initialize app life-cycle
            yield app

    def test_on_startup(self, app):
        assert isinstance(app.sqlalchemy.engine, AsyncEngine)
        assert isinstance(app.sqlalchemy.metadata, sqlalchemy.MetaData)

    def test_on_startup_no_database(self):
        app = Flama()
        with TestClient(app):  # Initialize app life-cycle
            assert app.sqlalchemy.database is None
            assert app.sqlalchemy.engine is None
            assert isinstance(app.sqlalchemy.metadata, sqlalchemy.MetaData)

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="MagicMock cannot mock async methods until 3.8"
    )  # PORT: Remove when Python3.7 EOL
    async def test_shutdown(self, app):
        module = SQLAlchemyModule(Mock(spec=Flama), "sqlite+aiosqlite://")

        with patch.object(module, "engine", dispose=AsyncMock(), __bool__=Mock(return_value=True)) as engine_mock:
            await module.on_shutdown()

        assert engine_mock.dispose.call_args_list == [call()]

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="MagicMock cannot mock async methods until 3.8"
    )  # PORT: Remove when Python3.7 EOL
    async def test_shutdown_no_database(self, app):
        module = SQLAlchemyModule(Mock(spec=Flama))

        with patch.object(module, "engine", dispose=AsyncMock(), __bool__=Mock(return_value=False)) as engine_mock:
            await module.on_shutdown()

        assert engine_mock.dispose.call_args_list == []
