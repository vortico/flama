import abc
import logging
import re
import typing as t

from flama import concurrency, exceptions, types
from flama.middleware import Middleware
from flama.telemetry.data_structures import Error, Response, TelemetryData

logger = logging.getLogger(__name__)

__all__ = ["TelemetryMiddleware"]

_MAX_BODY: t.Final = 64 * 1024

HookFunction = t.Callable[[TelemetryData], None | t.Awaitable[None]]


class Wrapper(abc.ABC):
    def __init__(self, app: types.App, data: TelemetryData, *, max_body: int | None) -> None:
        self.app = app
        self.data = data
        self._max_body = max_body
        self._response = Response(headers=None)

    @classmethod
    def build(
        cls, type: t.Literal["http", "websocket"], app: types.App, data: TelemetryData, *, max_body: int | None
    ) -> "Wrapper":
        if type == "websocket":
            return WebSocketWrapper(app, data, max_body=max_body)

        return HTTPWrapper(app, data, max_body=max_body)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        self._scope = scope
        self._receive = receive
        self._send = send

        try:
            await self.app(self._scope, self.receive, self.send)
            self.data.response = self._response
        except Exception as e:
            self.data.error = await Error.from_exception(exception=e)
            raise

    @abc.abstractmethod
    async def receive(self) -> types.Message: ...

    @abc.abstractmethod
    async def send(self, message: types.Message) -> None: ...


class HTTPWrapper(Wrapper):
    async def receive(self) -> types.Message:
        message = await self._receive()

        if message["type"] == "http.request":
            self.data.request.body.append(message.get("body", b""), self._max_body)

        return message

    async def send(self, message: types.Message) -> None:
        if message["type"] == "http.response.start":
            self._response.headers = {k.decode(): v.decode() for (k, v) in message.get("headers", [])}
            self._response.status_code = message.get("status")
        elif message["type"] == "http.response.body":
            self._response.body.append(message.get("body", b""), self._max_body)

        await self._send(message)


class WebSocketWrapper(Wrapper):
    async def receive(self) -> types.Message:
        message = await self._receive()

        if message["type"] == "websocket.receive":
            self.data.request.body.append(message.get("bytes", message.get("text", "").encode()), self._max_body)
        elif message["type"] == "websocket.disconnect":
            self._response.status_code = message.get("code", None)
            self._response.body.content = message.get("reason", "").encode()

        return message

    async def send(self, message: types.Message) -> None:
        if message["type"] == "websocket.send":
            self._response.body.append(message.get("bytes", message.get("text", "").encode()), self._max_body)
        elif message["type"] == "websocket.close":
            self._response.status_code = message.get("code")
            self._response.body.content = message.get("reason", "").encode()

        await self._send(message)


class TelemetryDataCollector:
    data: TelemetryData

    def __init__(
        self, app: types.ASGIApp, scope: types.Scope, receive: types.Receive, send: types.Send, *, max_body: int | None
    ) -> None:
        self.app = app
        self._scope = scope
        self._receive = receive
        self._send = send
        self._max_body = max_body

    @classmethod
    async def build(
        cls,
        app: types.ASGIApp,
        scope: types.Scope,
        receive: types.Receive,
        send: types.Send,
        *,
        max_body: int | None,
    ) -> "TelemetryDataCollector":
        self = cls(app, scope, receive, send, max_body=max_body)
        self.data = await TelemetryData.from_scope(scope=scope, receive=receive, send=send)
        return self

    async def __call__(self) -> None:
        await Wrapper.build(self._scope["type"], t.cast(types.App, self.app), self.data, max_body=self._max_body)(
            scope=self._scope, receive=self._receive, send=self._send
        )


class TelemetryMiddleware(Middleware):
    """Middleware that records an audit of every request and hands it to the given hooks.

    :param log_level: Level at which the record is logged.
    :param before: Hook called with the record before the request is handled.
    :param after: Hook called with the record once the request has been handled.
    :param tag: Route tag consulted to opt a route out of being recorded.
    :param ignored: Patterns of paths that are not recorded.
    :param max_body: Bytes of a request or response payload the record keeps, past which it keeps the head
        and marks the payload as truncated. ``None`` keeps every byte, and zero keeps none at all.
    """

    def __init__(
        self,
        *,
        log_level: int = logging.NOTSET,
        before: HookFunction | None = None,
        after: HookFunction | None = None,
        tag: str = "telemetry",
        ignored: list[str] = [],
        max_body: int | None = _MAX_BODY,
    ) -> None:
        self._log_level = log_level
        self._before = before
        self._after = after
        self._tag = tag
        self._ignored = [re.compile(x) for x in ignored]
        self._max_body = max_body

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if (
            scope["type"] not in ("http", "websocket")
            or any(pattern.match(scope["path"]) for pattern in self._ignored)
            or not self._get_tag(scope)
        ):
            await self.app(scope, receive, send)
            return

        collector = await TelemetryDataCollector.build(self.app, scope, receive, send, max_body=self._max_body)

        await self.before(collector.data)

        try:
            await collector()
        finally:
            await self.after(collector.data)
            logger.log(self._log_level, "Telemetry: %s", str(collector.data))

    async def before(self, data: TelemetryData) -> None:
        if self._before:
            await concurrency.run(self._before, data)

    async def after(self, data: TelemetryData) -> None:
        if self._after:
            await concurrency.run(self._after, data)

    def _get_tag(self, scope: types.Scope) -> bool:
        try:
            app: types.App = scope["app"]
            route, _ = app.router.resolve_route(scope)
            return route.tags.get(self._tag, True)
        except (exceptions.MethodNotAllowedException, exceptions.NotFoundException):
            return False
