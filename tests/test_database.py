import sys
from unittest.mock import Mock, call, patch

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine

from flama import Flama
from flama.database import DatabaseModule

if sys.version_info >= (3, 8):  # PORT: Remove when Python3.7 EOL
    from unittest.mock import AsyncMock


class TestCaseDatabaseModule:
    @pytest.fixture
    def app(self):
        return Flama(database="sqlite+aiosqlite://")

    def test_init(self, app):
        assert isinstance(app.database.engine, AsyncEngine)
        assert isinstance(app.database.metadata, sqlalchemy.MetaData)

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="MagicMock cannot mock async methods until 3.8"
    )  # PORT: Remove when Python3.7 EOL
    async def test_shutdown(self, app):
        module = DatabaseModule(Mock(spec=Flama), "sqlite+aiosqlite://")

        with patch.object(module, "engine", dispose=AsyncMock(), __bool__=Mock(return_value=True)) as engine_mock:
            await module.on_shutdown()

        assert engine_mock.dispose.call_args_list == [call()]

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="MagicMock cannot mock async methods until 3.8"
    )  # PORT: Remove when Python3.7 EOL
    async def test_shutdown_no_database(self, app):
        module = DatabaseModule(Mock(spec=Flama))

        with patch.object(module, "engine", dispose=AsyncMock(), __bool__=Mock(return_value=False)) as engine_mock:
            await module.on_shutdown()

        assert engine_mock.dispose.call_args_list == []
