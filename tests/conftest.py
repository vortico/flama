import re
import tempfile
import warnings
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


@pytest.fixture(scope="function")
def exception(request):
    if request.param is None:
        context = ExceptionContext(ExitStack())
    elif isinstance(request.param, Exception):
        context = ExceptionContext(
            pytest.raises(request.param.__class__, match=re.escape(str(request.param))), request.param
        )
    elif isinstance(request.param, (list, tuple)):
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
async def client(app):
    async with Client(app=app) as client:
        assert client.app.status == types.AppStatus.READY
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
                tf.keras.Input((2,)),
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
    if not installed(request.param) or not installed("numpy"):
        pytest.skip(f"Lib '{request.param}' is not installed.")

    return model_factory.model(request.param)


@pytest.fixture(scope="function")
def serialized_model_class(request):
    if not installed(request.param) or not installed("numpy"):
        pytest.skip(f"Lib '{request.param}' is not installed.")

    return model_factory.model_cls(request.param)


@pytest.fixture(scope="function")
def model_path(request):
    if not installed(request.param) or not installed("numpy"):
        pytest.skip(f"Lib '{request.param}' is not installed.")

    with tempfile.NamedTemporaryFile(suffix=".flm") as f:
        flama.dump(model_factory.model(request.param), f.name)
        f.flush()

        yield Path(f.name)
