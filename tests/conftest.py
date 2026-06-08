# Pre-import TensorFlow before anything else so its OpenMP runtime binds first. ``import flama``
# transitively loads ``mlx_lm`` (and through it ``torch`` / ``transformers`` / ``sklearn``); on
# Apple Silicon, ``sklearn`` ships its own ``libomp.dylib`` which initialises a thread pool that
# deadlocks TF's eager runtime if TF binds OpenMP afterwards. Importing TF first sidesteps the
# clash so subsequent ``model.fit`` calls don't hang inside
# ``_initialize_uninitialized_variables``.
try:
    import tensorflow  # noqa: F401
except Exception:  # pragma: no cover
    pass

import logging
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
        message = str(request.param)
        context = ExceptionContext(
            pytest.raises(request.param.__class__, match=re.escape(message) if message else None), request.param
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


@pytest.fixture(scope="function", params=["bz2", "lzma", "zlib", "zstd"])
def compression_format(request):
    return request.param


@pytest.fixture(autouse=True)
def clear_metadata():
    metadata.clear()


@pytest.fixture(autouse=True)
def clear_pagination():
    paginator.schemas = {}


@pytest.fixture(scope="function")
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
            model = model_factory.model(request.param)
            family = model_factory.family(request.param)
            lib = model_factory.lib(request.param)
            artifacts = model_factory.artifacts(request.param)
            config = model_factory.config(request.param)
            flama.dump(model, path=f.name, family=family, artifacts=artifacts, config=config, lib=lib)
            f.flush()

            yield Path(f.name)
    except NotInstalled as e:
        pytest.skip(f"Lib '{str(e)}' is not installed.")


@pytest.fixture(scope="function")
def caplog_flama(caplog: pytest.LogCaptureFixture) -> t.Iterator[pytest.LogCaptureFixture]:
    """Variant of :fixture:`caplog` that also captures records emitted by the ``flama`` logger.

    The runtime ``dictConfig`` (applied by ``Config.run`` and re-applied by uvicorn) sets
    ``propagate=False`` on the ``flama`` logger so its themed Rich handler does not compete with
    uvicorn's root-bound default handlers. As a side effect, pytest's stock ``caplog`` (whose
    handler is bound to the root logger) cannot see those records. This fixture attaches
    ``caplog.handler`` directly to the ``flama`` logger for the duration of the test so the
    framework's breadcrumbs show up in ``caplog.records``.
    """
    flama_logger = logging.getLogger("flama")
    flama_logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        flama_logger.removeHandler(caplog.handler)
