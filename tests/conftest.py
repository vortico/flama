import asyncio
import tempfile
import typing as t
import warnings
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock

import marshmallow
import pydantic
import pytest
import sqlalchemy
import typesystem
from faker import Faker

import flama
from flama import Flama
from flama.sqlalchemy import SQLAlchemyModule, metadata
from flama.testclient import TestClient
from tests.utils import ExceptionContext, installed

try:
    import numpy as np
except Exception:
    warnings.warn("Numpy not installed")
    np = None

try:
    import sklearn.compose
    import sklearn.impute
    import sklearn.neural_network
    import sklearn.pipeline
except Exception:
    warnings.warn("SKLearn not installed")
    sklearn = None

try:
    import tensorflow as tf
except Exception:
    warnings.warn("Tensorflow not installed")
    tf = None

try:
    import torch
except Exception:
    warnings.warn("Torch not installed")
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

    if schemas.lib == pydantic:
        schema_ = pydantic.create_model("Puppy", custom_id=(t.Optional[int], None), name=(str, ...))
    elif schemas.lib == typesystem:
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
    params=[
        pytest.param("pydantic", id="pydantic"),
        pytest.param("typesystem", id="typesystem"),
        pytest.param("marshmallow", id="marshmallow"),
    ],
)
def app(request):
    return Flama(
        title="Foo",
        version="0.1",
        description="Bar",
        schema="/schema/",
        docs="/docs/",
        modules={SQLAlchemyModule("sqlite+aiosqlite://")},
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


class ModelFactory:
    def __init__(self):
        self._factories = {
            "sklearn": self._sklearn,
            "sklearn-pipeline": self._sklearn_pipeline,
            "tensorflow": self._tensorflow,
            "torch": self._torch,
        }

        self._models = {}
        self._models_cls = {}

    def _build(self, framework: str):
        if framework not in self._factories:
            raise ValueError(f"Wrong framework: '{framework}'.")

        if framework not in self._models:
            self._models[framework], self._models_cls[framework] = self._factories[framework]()

    def model(self, framework: str):
        self._build(framework)
        return self._models[framework]

    def model_cls(self, framework: str):
        self._build(framework)
        return self._models_cls[framework]

    def _sklearn(self):
        model = sklearn.neural_network.MLPClassifier(activation="tanh", max_iter=2000, hidden_layer_sizes=(10,))
        model.fit(
            np.array([[0, 0], [0, 1], [1, 0], [1, 1]]),
            np.array([0, 1, 1, 0]),
        )
        return model, sklearn.neural_network.MLPClassifier

    def _sklearn_pipeline(self):
        model = sklearn.neural_network.MLPClassifier(activation="tanh", max_iter=2000, hidden_layer_sizes=(10,))
        numerical_transformer = sklearn.pipeline.Pipeline(
            [
                ("imputer", sklearn.impute.SimpleImputer(strategy="constant", fill_value=0)),
            ]
        )
        preprocess = sklearn.compose.ColumnTransformer(
            [
                ("numerical", numerical_transformer[0, 1]),
            ]
        )
        pipeline = sklearn.pipeline.Pipeline(
            [
                ("preprocess", preprocess),
                ("model", model),
            ]
        )

        pipeline.fit(
            np.array([[0, np.nan], [np.nan, 1], [1, 0], [1, 1]]),  # NaN will be replaced with 0
            np.array([0, 1, 1, 0]),
        )

        return pipeline, sklearn.pipeline.Pipeline

    def _tensorflow(self):
        model = tf.keras.models.Sequential(
            [
                tf.keras.layers.Flatten(input_shape=(2,)),
                tf.keras.layers.Dense(10, activation="tanh"),
                tf.keras.layers.Dense(1, activation="sigmoid"),
            ]
        )

        model.compile(optimizer="adam", loss="mse")
        model.fit(
            np.array([[0, 0], [0, 1], [1, 0], [1, 1]]),
            np.array([[0], [1], [1], [0]]),
            epochs=2000,
            verbose=0,
        )

        return model, tf.keras.models.Sequential

    def _torch(self):
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.l1 = torch.nn.Linear(2, 10)
                self.l2 = torch.nn.Linear(10, 1)

            def forward(self, x):
                x = torch.tanh(self.l1(x))
                x = torch.sigmoid(self.l2(x))
                return x

            def _train(self, X, Y, loss, optimizer):
                for m in self.modules():
                    if isinstance(m, torch.nn.Linear):
                        m.weight.data.normal_(0, 1)

                steps = X.size(0)
                for i in range(2000):
                    for j in range(steps):
                        data_point = np.random.randint(steps)
                        x_var = torch.autograd.Variable(X[data_point], requires_grad=False)
                        y_var = torch.autograd.Variable(Y[data_point], requires_grad=False)

                        optimizer.zero_grad()
                        y_hat = model(x_var)
                        loss_result = loss.forward(y_hat, y_var)
                        loss_result.backward()
                        optimizer.step()

                return self

        X = torch.Tensor([[0, 0], [0, 1], [1, 0], [1, 1]])
        Y = torch.Tensor([0, 1, 1, 0]).view(-1, 1)
        model = Model()
        model._train(X, Y, loss=torch.nn.BCELoss(), optimizer=torch.optim.Adam(model.parameters()))

        return model, torch.jit.RecursiveScriptModule


model_factory = ModelFactory()


@pytest.fixture(scope="function")
def model(request):
    if not installed(request.param):
        pytest.skip(f"Lib '{request.param}' is not installed.")
        return

    return model_factory.model(request.param)


@pytest.fixture(scope="function")
def serialized_model_class(request):
    if not installed(request.param):
        pytest.skip(f"Lib '{request.param}' is not installed.")
        return

    return model_factory.model_cls(request.param)


@pytest.fixture(scope="function")
def model_path(request):
    if not installed(request.param):
        pytest.skip(f"Lib '{request.param}' is not installed.")
        return

    with tempfile.NamedTemporaryFile(suffix=".flm") as f:
        flama.dump(model_factory.model(request.param), f.name)
        f.flush()

        yield Path(f.name)
