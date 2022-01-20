import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from flama import Flama
from flama.database import DatabaseModule


class TestCaseDatabaseModule:
    @pytest.fixture
    def app(self):
        return Flama(database="sqlite+aiosqlite://")

    def test_init(self, app):
        assert isinstance(app.database.engine, AsyncEngine)
        assert isinstance(app.database.metadata, sqlalchemy.MetaData)
        assert app.database.connection is None

    async def test_startup_and_shutdown(self, app):
        module = DatabaseModule(app, "sqlite+aiosqlite://")
        assert module.connection is None
        await module.on_startup()
        assert isinstance(module.connection, AsyncConnection)
        await module.on_shutdown()
        assert module.connection is None

    async def test_startup_and_shutdown_no_database(self, app):
        module = DatabaseModule(app)
        assert module.connection is None
        await module.on_startup()
        assert module.connection is None
        await module.on_shutdown()
        assert module.connection is None
