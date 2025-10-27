import re
import tempfile
import typing as t
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from faker import Faker

import flama
from flama import Flama, types
from flama.client import Client
from flama.pagination import paginator
from flama.sqlalchemy import SQLAlchemyModule, metadata
from tests._utils import ExceptionContext, NotInstalled, model_factory

DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="function")
def exception(request):
    if request.param is None:
        context = ExceptionContext(ExitStack())
    elif isinstance(request.param, Exception):
        context = ExceptionContext(
            pytest.raises(request.param.__class__, match=re.escape(str(request.param))), request.param
        )
    elif isinstance(request.param, list | tuple):
        exception, message = request.param
        context = ExceptionContext(pytest.raises(exception, match=re.escape(message)), exception)
    else:
        context = ExceptionContext(pytest.raises(request.param), request.param)
    return context


@pytest.fixture(scope="session")
def fake():
    return Faker()


@pytest.fixture(autouse=True)
def clear_metadata():
    metadata.clear()


@pytest.fixture(autouse=True)
def clear_pagination():
    paginator.schemas = {}


@pytest.fixture
def openapi_spec():
    return {"info": {"title": "Foo", "version": "1.0.0", "description": "Bar"}}


@pytest.fixture(
    scope="function",
    params=[
        pytest.param("pydantic", id="pydantic"),
        pytest.param("typesystem", id="typesystem"),
        pytest.param("marshmallow", id="marshmallow"),
    ],
)
def app(request, openapi_spec):
    return Flama(
        openapi=openapi_spec,
        schema="/schema/",
        docs="/docs/",
        modules={SQLAlchemyModule("sqlite+aiosqlite://")},
        schema_library=request.param,
    )


@pytest.fixture(scope="function")
async def client(app: Flama):
    async with Client(app=app) as client:
        assert t.cast(Flama, client.app).status == types.AppStatus.READY
        yield client


@pytest.fixture(scope="function")
def asgi_scope():
    return {
        "app": Flama(),
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "root_path": "",
        "query_string": b"",
        "headers": [],
    }


@pytest.fixture(scope="function")
def asgi_receive():
    return AsyncMock()


@pytest.fixture(scope="function")
def asgi_send():
    return AsyncMock()


@pytest.fixture(scope="function")
def model(request):
    try:
        return model_factory.model(request.param)
    except NotInstalled as e:
        pytest.skip(f"Lib '{str(e)}' is not installed.")


@pytest.fixture(scope="function")
def serialized_model_class(request):
    try:
        return model_factory.model_cls(request.param)
    except NotInstalled as e:
        pytest.skip(f"Lib '{str(e)}' is not installed.")


@pytest.fixture(scope="function")
def model_path(request):
    try:
        with tempfile.NamedTemporaryFile(suffix=".flm") as f:
            flama.dump(model_factory.model(request.param), path=f.name)
            f.flush()

            yield Path(f.name)
    except NotInstalled as e:
        pytest.skip(f"Lib '{str(e)}' is not installed.")
