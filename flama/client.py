import asyncio
import functools
import importlib.metadata
import logging
import typing as t
from types import TracebackType

import httpx

from flama import types
from flama.applications import Flama

__all__ = ["Client", "LifespanContextManager"]

logger = logging.getLogger(__name__)


class LifespanContextManager:
    def __init__(self, app: "Flama", timeout: float = 60.0):
        self.app = app
        self.timeout = timeout
        self._startup_complete = asyncio.Event()
        self._shutdown_complete = asyncio.Event()
        self._receive_queue = asyncio.Queue(maxsize=2)
        self._exception: t.Optional[BaseException] = None

    async def _startup(self) -> None:
        await self._receive_queue.put(types.Message({"type": "lifespan.startup"}))
        await asyncio.wait_for(self._startup_complete.wait(), timeout=self.timeout)
        if self._exception:
            raise self._exception

    async def _shutdown(self) -> None:
        await self._receive_queue.put(types.Message({"type": "lifespan.shutdown"}))
        await asyncio.wait_for(self._shutdown_complete.wait(), timeout=self.timeout)

    async def _receive(self) -> types.Message:
        return await self._receive_queue.get()

    async def _send(self, message: types.Message) -> None:
        if message["type"] == "lifespan.startup.complete":
            self._startup_complete.set()
        elif message["type"] == "lifespan.shutdown.complete":
            self._shutdown_complete.set()

    async def _app_task(self) -> None:
        scope = types.Scope({"type": "lifespan"})

        try:
            await self.app(scope, self._receive, self._send)
        except BaseException as exc:
            self._exception = exc
            self._startup_complete.set()
            self._shutdown_complete.set()

            raise

    async def __aenter__(self) -> "LifespanContextManager":
        task = asyncio.create_task(self._app_task())

        try:
            await self._startup()
        except BaseException:
            raise
        finally:
            await task

        return self

    async def __aexit__(
        self,
        exc_type: t.Optional[type[BaseException]] = None,
        exc_value: t.Optional[BaseException] = None,
        traceback: t.Optional[TracebackType] = None,
    ):
        task = asyncio.create_task(self._app_task())

        try:
            await self._shutdown()
        except BaseException:
            raise
        finally:
            await task


class Client(httpx.AsyncClient):
    """A client for interacting with a Flama application either remote or local.

    This client can handle a local python object:
    >>> client = Client(app=Flama())

    Or connect to a remote API:
    >>> client = Client(base_url="https://foo.bar")

    Or generate a Flama application based on a set of flm model files:
    >>> client = Client(models=[("foo", "/foo/", "model_foo.flm"), ("bar", "/bar/", "model_bar.flm")])

    For initializing the application it's required to use it as an async context manager:
    >>> async with Client(app=Flama()) as client:
    >>>     client.post(...)
    """

    def __init__(
        self,
        /,
        app: t.Optional["Flama"] = None,
        models: t.Optional[t.Sequence[tuple[str, str, str]]] = None,
        **kwargs,
    ):
        self.models: t.Optional[dict[str, str]] = None

        if models:
            app = Flama() if not app else app
            for name, url, path in models:
                app.models.add_model(url, path, name)

            self.models = {m[0]: m[1] for m in models or {}}

        self.lifespan = LifespanContextManager(app) if app else None
        self.app = app

        kwargs.setdefault("transport", httpx.ASGITransport(app=app) if app else None)  # type: ignore
        kwargs.setdefault("base_url", "http://localapp")
        kwargs["headers"] = {"user-agent": f"flama/{importlib.metadata.version('flama')}", **kwargs.get("headers", {})}

        super().__init__(**kwargs)

    async def __aenter__(self) -> "Client":
        if self.lifespan:
            await self.lifespan.__aenter__()
        await super().__aenter__()

        return self

    async def __aexit__(
        self,
        exc_type: t.Optional[type[BaseException]] = None,
        exc_value: t.Optional[BaseException] = None,
        traceback: t.Optional[TracebackType] = None,
    ):
        await super().__aexit__(exc_type, exc_value, traceback)
        if self.lifespan:
            await self.lifespan.__aexit__(exc_type, exc_value, traceback)

    def model_request(self, model: str, method: str, url: str, **kwargs) -> t.Awaitable[httpx.Response]:
        assert self.models, "No models found for request."
        return self.request(method, f"{self.models[model].rstrip('/')}{url}", **kwargs)

    model_inspect = functools.partialmethod(model_request, method="GET", url="/")
    model_predict = functools.partialmethod(model_request, method="POST", url="/predict/")
