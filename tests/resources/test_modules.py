import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine

from flama import Flama


class TestCaseDatabaseModule:
    @pytest.fixture
    def app(self):
        return Flama(database="sqlite+aiosqlite://")

    def test_init(self, app):
        assert isinstance(app.database.engine, AsyncEngine)
        assert isinstance(app.database.metadata, sqlalchemy.MetaData)
