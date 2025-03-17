import abc
import logging
import re
import typing as t

from flama import Flama, concurrency, exceptions, types
from flama.telemetry.data_structures import Error, Response, TelemetryData

logger = logging.getLogger(__name__)

__all__ = ["TelemetryMiddleware"]


PROJECT = "vortico-core"
SERVICE = "elektrococo"
TOPIC_ID = "telemetry-bus"

HookFunction = t.Callable[[TelemetryData], t.Union[None, t.Awaitable[None]]]


class Wrapper(abc.ABC):
    def __init__(self, app: Flama, data: TelemetryData) -> None:
        self.app = app
        self.data = data

    @classmethod
    def build(cls, type: t.Literal["http", "websocket"], app: Flama, data: TelemetryData) -> "Wrapper":
        if type == "websocket":
            return WebSocketWrapper(app, data)

        return HTTPWrapper(app, data)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        self._scope = scope
        self._receive = receive
        self._send = send
        self._response_body = b""
        self._response_headers = None
        self._response_status_code = None

        try:
            await self.app(self._scope, self.receive, self.send)
            self.data.response = Response(
                headers=self._response_headers, body=self._response_body, status_code=self._response_status_code
            )
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
            self.data.request.body += message.get("body", b"")

        return message

    async def send(self, message: types.Message) -> None:
        if message["type"] == "http.response.start":
            self._response_headers = {k.decode(): v.decode() for (k, v) in message.get("headers", [])}
            self._response_status_code = message.get("status")
        elif message["type"] == "http.response.body":
            self._response_body += message.get("body", b"")

        await self._send(message)


class WebSocketWrapper(Wrapper):
    async def receive(self) -> types.Message:
        message = await self._receive()

        if message["type"] == "websocket.receive":
            self._response_body += message.get("body", b"")
        elif message["type"] == "websocket.disconnect":
            self._response_status_code = message.get("code", None)
            self._response_body = message.get("reason", "").encode()

        return message

    async def send(self, message: types.Message) -> None:
        if message["type"] == "websocket.send":
            self.data.request.body += message.get("bytes", message.get("text", "").encode())
        elif message["type"] == "websocket.close":
            self._response_status_code = message.get("code")
            self._response_body = message.get("reason", "").encode()

        await self._send(message)


class TelemetryDataCollector:
    data: TelemetryData

    def __init__(self, app: Flama, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        self.app = app
        self._scope = scope
        self._receive = receive
        self._send = send

    @classmethod
    async def build(
        cls, app: Flama, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> "TelemetryDataCollector":
        self = cls(app, scope, receive, send)
        self.data = await TelemetryData.from_scope(scope=scope, receive=receive, send=send)
        return self

    async def __call__(self) -> None:
        await Wrapper.build(self._scope["type"], self.app, self.data)(
            scope=self._scope, receive=self._receive, send=self._send
        )


class TelemetryMiddleware:
    def __init__(
        self,
        app: types.App,
        *,
        log_level: int = logging.NOTSET,
        before: t.Optional[HookFunction] = None,
        after: t.Optional[HookFunction] = None,
        tag: str = "telemetry",
        ignored: list[str] = [],
    ) -> None:
        self.app: Flama = t.cast(Flama, app)
        self._log_level = log_level
        self._before = before
        self._after = after
        self._tag = tag
        self._ignored = [re.compile(x) for x in ignored]

    async def before(self, data: TelemetryData):
        if self._before:
            await concurrency.run(self._before, data)

    async def after(self, data: TelemetryData):
        if self._after:
            await concurrency.run(self._after, data)

    def _get_tag(self, scope: "types.Scope") -> bool:
        try:
            app: Flama = scope["app"]
            route, _ = app.router.resolve_route(scope)
            return route.tags.get(self._tag, True)
        except (exceptions.MethodNotAllowedException, exceptions.NotFoundException):
            return False

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if (
            scope["type"] not in ("http", "websocket")
            or any(pattern.match(scope["path"]) for pattern in self._ignored)
            or not self._get_tag(scope)
        ):
            await self.app(scope, receive, send)
            return

        collector = await TelemetryDataCollector.build(self.app, scope, receive, send)

        await self.before(collector.data)

        try:
            await collector()
        finally:
            await self.after(collector.data)
            logger.log(self._log_level, "Telemetry: %s", str(collector.data))
