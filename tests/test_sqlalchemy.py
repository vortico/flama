from unittest.mock import AsyncMock, Mock, call, patch

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine

from flama import Flama
from flama.client import Client
from flama.sqlalchemy import SQLAlchemyModule


class TestCaseSQLAlchemyModule:
    @pytest.fixture
    async def app(self):
        app = Flama(modules={SQLAlchemyModule("sqlite+aiosqlite://")})
        async with Client(app):  # Initialize app life-cycle
            yield app

    def test_on_startup(self, app):
        assert isinstance(app.sqlalchemy.engine, AsyncEngine)
        assert isinstance(app.sqlalchemy.metadata, sqlalchemy.MetaData)

    async def test_on_startup_no_database(self):
        app = Flama(modules={SQLAlchemyModule()})
        async with Client(app):  # Initialize app life-cycle
            assert app.sqlalchemy.database is None
            assert app.sqlalchemy.engine is None
            assert isinstance(app.sqlalchemy.metadata, sqlalchemy.MetaData)

    async def test_shutdown(self, app):
        module = SQLAlchemyModule("sqlite+aiosqlite://")

        with patch.object(module, "engine", dispose=AsyncMock(), __bool__=Mock(return_value=True)) as engine_mock:
            await module.on_shutdown()

        assert engine_mock.dispose.call_args_list == [call()]

    async def test_shutdown_no_database(self, app):
        module = SQLAlchemyModule()

        with patch.object(module, "engine", dispose=AsyncMock(), __bool__=Mock(return_value=False)) as engine_mock:
            await module.on_shutdown()

        assert engine_mock.dispose.call_args_list == []
