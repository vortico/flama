import asyncio
import sys
from contextlib import ExitStack
from pathlib import Path

import marshmallow
import pytest
import sqlalchemy
import typesystem
from faker import Faker

from flama import Flama
from flama.sqlalchemy import metadata
from flama.testclient import TestClient
from tests.utils import ExceptionContext, check_param_lib_installed

if sys.version_info >= (3, 8):  # PORT: Remove when stop supporting 3.7 # pragma: no cover
    from unittest.mock import AsyncMock
else:  # pragma: no cover
    from asyncmock import AsyncMock

try:
    import sklearn
    from sklearn.linear_model import LogisticRegression
except Exception:
    sklearn = None

try:
    import tensorflow as tf
except Exception:
    tf = None

try:
    import torch
except Exception:
    torch = None

DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def exception(request):
    if request.param is None:
        context = ExceptionContext(ExitStack())
    elif isinstance(request.param, Exception):
        context = ExceptionContext(
            pytest.raises(request.param.__class__, match=getattr(request.param, "message", None)), request.param
        )
    else:
        context = ExceptionContext(pytest.raises(request.param), request.param)
    return context


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
            {"custom_id": marshmallow.fields.Integer(allow_none=True), "name": marshmallow.fields.String()},
        )
    else:
        raise ValueError("Wrong schema lib")

    app.schema.schemas["Puppy"] = schema_
    return schema_


@pytest.fixture(scope="function")
async def puppy_model(app, client):
    table = sqlalchemy.Table(
        "puppy",
        app.sqlalchemy.metadata,
        sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
        sqlalchemy.Column("name", sqlalchemy.String),
    )

    async with app.sqlalchemy.engine.begin() as connection:
        await connection.run_sync(app.sqlalchemy.metadata.create_all, tables=[table])

    yield table

    async with app.sqlalchemy.engine.begin() as connection:
        await connection.run_sync(app.sqlalchemy.metadata.drop_all, tables=[table])


@pytest.fixture(scope="session")
def fake():
    return Faker()


@pytest.fixture(autouse=True)
def clear_metadata():
    metadata.clear()


@pytest.fixture(
    scope="function",
    params=[pytest.param("typesystem", id="typesystem"), pytest.param("marshmallow", id="marshmallow")],
)
def app(request):
    return Flama(
        title="Foo",
        version="0.1",
        description="Bar",
        schema="/schema/",
        docs="/docs/",
        sqlalchemy_database="sqlite+aiosqlite://",
        schema_library=request.param,
    )


@pytest.fixture(scope="function")
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def asgi_scope():
    return {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "root_path": "/",
        "query_string": b"",
        "headers": [],
    }


@pytest.fixture(scope="function")
def asgi_receive():
    return AsyncMock()


@pytest.fixture(scope="function")
def asgi_send():
    return AsyncMock()


def sklearn_model():
    return LogisticRegression(), LogisticRegression


def tensorflow_model():
    tf_model = tf.keras.models.Sequential(
        [
            tf.keras.layers.Flatten(input_shape=(28, 28)),
            tf.keras.layers.Dense(128, activation="relu"),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(10, activation="softmax"),
        ]
    )

    tf_model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])

    return tf_model, tf.keras.models.Sequential


def torch_model():
    class Model(torch.nn.Module):
        def forward(self, x):
            return x + 10

    return Model(), torch.jit.RecursiveScriptModule


@pytest.fixture(scope="function")
@check_param_lib_installed
def model(request):
    return {"sklearn": sklearn_model, "tensorflow": tensorflow_model, "torch": torch_model}[request.param]()[0]


@pytest.fixture(scope="function")
@check_param_lib_installed
def serialized_model_class(request):
    return {"sklearn": sklearn_model, "tensorflow": tensorflow_model, "torch": torch_model}[request.param]()[1]


@pytest.fixture(scope="session")
def model_paths():
    return {
        "sklearn": Path("tests/data/sklearn_model.flm"),
        "tensorflow": Path("tests/data/tensorflow_model.flm"),
        "torch": Path("tests/data/pytorch_model.flm"),
    }


@pytest.fixture(scope="function")
@check_param_lib_installed
def model_path(request, model_paths):
    return model_paths[request.param]
