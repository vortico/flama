import asyncio

import databases
import marshmallow
import pytest
import sqlalchemy

DATABASE_URL = "sqlite:///test.db"


@pytest.yield_fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def database_metadata():
    return sqlalchemy.MetaData()


@pytest.fixture(scope="session")
async def database():
    async with databases.Database(DATABASE_URL) as db:
        yield db


@pytest.fixture(scope="session")
def schema():
    class PuppySchema(marshmallow.Schema):
        custom_id = marshmallow.fields.Integer(dump_only=True)
        name = marshmallow.fields.String()

    return PuppySchema


@pytest.fixture(scope="session")
def model(database_metadata):
    model_ = sqlalchemy.Table(
        "puppy",
        database_metadata,
        sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
        sqlalchemy.Column("name", sqlalchemy.String),
    )

    return model_
