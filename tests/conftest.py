import asyncio
from contextlib import ExitStack

import databases
import marshmallow
import pytest
import sqlalchemy
import typesystem
from faker import Faker
from starlette.testclient import TestClient

from flama import Flama, schemas

DATABASE_URL = "sqlite:///test.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def exception(request):
    if request.param is None:
        return ExitStack()

    if isinstance(request.param, Exception):
        return pytest.raises(request.param.__class__, match=getattr(request.param, "message", None))

    return pytest.raises(request.param)


@pytest.fixture(scope="function")
def database_metadata():
    return sqlalchemy.MetaData()


@pytest.fixture(scope="session")
async def database():
    async with databases.Database(DATABASE_URL) as db:
        yield db


@pytest.fixture(scope="function")
def puppy_schema(app):
    from flama import schemas

    if schemas.lib == typesystem:
        schema_ = typesystem.Schema(
            fields={"custom_id": typesystem.Integer(allow_null=True), "name": typesystem.String()}
        )
    elif schemas.lib == marshmallow:
        schema_ = type(
            "Puppy",
            (marshmallow.Schema,),
            {
                "custom_id": marshmallow.fields.Integer(allow_none=True),
                "name": marshmallow.fields.String(),
            },
        )
    else:
        raise ValueError("Wrong schema lib")

    app.schemas["Puppy"] = schema_
    return schema_


@pytest.fixture(scope="function")
def puppy_model(database_metadata):
    model_ = sqlalchemy.Table(
        "puppy",
        database_metadata,
        sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
        sqlalchemy.Column("name", sqlalchemy.String),
    )

    return model_


@pytest.fixture(scope="session")
def fake():
    return Faker()


# TODO: Unneeded?
@pytest.fixture(scope="module", autouse=True)
def enforce_typesystem():
    schemas._setup("typesystem")


@pytest.fixture(
    scope="function",
    params=[pytest.param("typesystem", id="typesystem"), pytest.param("marshmallow", id="marshmallow")],
)
def app(request):
    schemas._setup(request.param)

    return Flama(
        components=[],
        title="Foo",
        version="0.1",
        description="Bar",
        schema="/schema/",
        docs="/docs/",
        redoc="/redoc/",
    )


@pytest.fixture(scope="function")
def client(app):
    return TestClient(app)


def assert_recursive_contains(first, second):
    if isinstance(first, dict) and isinstance(second, dict):
        assert first.keys() <= second.keys()

        for k, v in first.items():
            assert_recursive_contains(v, second[k])
    elif isinstance(first, (list, set, tuple)) and isinstance(second, (list, set, tuple)):
        assert len(first) <= len(second)

        for i, _ in enumerate(first):
            assert_recursive_contains(first[i], second[i])
    else:
        assert first == second
