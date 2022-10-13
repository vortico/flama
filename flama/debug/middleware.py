import abc
import dataclasses
import inspect
import typing
from pathlib import Path

from flama import concurrency
from flama.debug.types import ErrorContext
from flama.exceptions import HTTPException, WebSocketException
from flama.http import PlainTextResponse, Request, Response
from flama.responses import APIErrorResponse, HTMLTemplateResponse
from flama.websockets import WebSocket

if typing.TYPE_CHECKING:
    from flama.asgi import App, Message, Receive, Scope, Send

__all__ = ["ServerErrorMiddleware", "ExceptionMiddleware"]

TEMPLATES_PATH = Path(__file__).parents[1].resolve() / "templates" / "debug"

Handler = typing.NewType("Handler", typing.Callable[[Request, Exception], Response])


class BaseErrorMiddleware(abc.ABC):
    def __init__(self, app: "App", debug: bool = False) -> None:
        self.app = app
        self.debug = debug

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def sender(message: "Message") -> None:
            nonlocal response_started, send

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, sender)
        except Exception as exc:
            await self.process_exception(scope, receive, send, exc, response_started)

    @abc.abstractmethod
    async def process_exception(
        self, scope: "Scope", receive: "Receive", send: "Send", exc: Exception, response_started: bool
    ) -> None:
        ...


class ServerErrorMiddleware(BaseErrorMiddleware):
    def _get_handler(self) -> Handler:
        return self.debug_response if self.debug else self.error_response

    async def process_exception(
        self, scope: "Scope", receive: "Receive", send: "Send", exc: Exception, response_started: bool
    ) -> None:
        handler = self._get_handler()
        response = handler(Request(scope), exc)

        if not response_started:
            await response(scope, receive, send)

        # We always continue to raise the exception.
        # This allows servers to log the error, or test clients to optionally raise the error within the test case.
        raise exc

    def debug_response(self, request: Request, exc: Exception) -> Response:
        accept = request.headers.get("accept", "")

        if "text/html" in accept:
            return HTMLTemplateResponse(
                "debug/error_500.html", context=dataclasses.asdict(ErrorContext.build(request, exc))
            )
        return PlainTextResponse("Internal Server Error", status_code=500)

    def error_response(self, request: Request, exc: Exception) -> Response:
        return PlainTextResponse("Internal Server Error", status_code=500)


class ExceptionMiddleware(BaseErrorMiddleware):
    def __init__(
        self, app: "App", handlers: typing.Optional[typing.Mapping[typing.Any, Handler]] = None, debug: bool = False
    ):
        super().__init__(app, debug)
        handlers = handlers or {}
        self._status_handlers: typing.Dict[int, typing.Callable] = {
            status_code: handler for status_code, handler in handlers.items() if isinstance(status_code, int)
        }
        self._exception_handlers: typing.Dict[typing.Type[Exception], typing.Callable] = {
            HTTPException: self.http_exception,
            WebSocketException: self.websocket_exception,
            **{e: handler for e, handler in handlers.items() if inspect.isclass(e) and issubclass(e, Exception)},
        }

    def add_exception_handler(
        self,
        handler: Handler,
        status_code: typing.Optional[int] = None,
        exc_class: typing.Optional[typing.Type[Exception]] = None,
    ) -> None:
        if status_code is None and exc_class is None:
            raise ValueError("Status code or exception class must be defined")

        if status_code is not None:
            self._status_handlers[status_code] = handler

        if exc_class is not None:
            self._exception_handlers[exc_class] = handler

    def _get_handler(self, exc: Exception) -> Handler:
        if isinstance(exc, HTTPException) and exc.status_code in self._status_handlers:
            return self._status_handlers[exc.status_code]
        else:
            try:
                return next(
                    self._exception_handlers[cls] for cls in type(exc).__mro__ if cls in self._exception_handlers
                )
            except StopIteration:
                raise exc

    async def process_exception(
        self, scope: "Scope", receive: "Receive", send: "Send", exc: Exception, response_started: bool
    ) -> None:
        handler = self._get_handler(exc)

        if response_started:
            raise RuntimeError("Caught handled exception, but response already started.") from exc

        if scope["type"] == "http":
            request = Request(scope, receive=receive)
            response = await concurrency.run(handler, request, exc)
            await response(scope, receive, send)
        elif scope["type"] == "websocket":
            websocket = WebSocket(scope, receive=receive, send=send)
            await concurrency.run(handler, websocket, exc)

    def http_exception(self, request: Request, exc: HTTPException) -> Response:
        if exc.status_code in {204, 304}:
            return Response(status_code=exc.status_code, headers=exc.headers)

        accept = request.headers.get("accept", "")

        if self.debug and exc.status_code == 404 and "text/html" in accept:
            return PlainTextResponse(content=exc.detail, status_code=exc.status_code)

        return APIErrorResponse(detail=exc.detail, status_code=exc.status_code, exception=exc)

    async def websocket_exception(self, websocket: WebSocket, exc: WebSocketException) -> None:
        await websocket.close(code=exc.code, reason=exc.reason)
