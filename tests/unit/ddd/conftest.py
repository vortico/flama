import pytest

from flama import Flama
from flama.sqlalchemy import SQLAlchemyModule


@pytest.fixture(scope="function")
def app():
    return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})
