import abc
import dataclasses
import inspect
import logging
import typing as t
from pathlib import Path

import starlette.exceptions

from flama import concurrency, exceptions, http, types, websockets
from flama.debug.data_structures import ErrorContext, NotFoundContext

if t.TYPE_CHECKING:
    from flama.debug.types import Handler

logger = logging.getLogger(__name__)

__all__ = ["ServerErrorMiddleware", "ExceptionMiddleware"]

TEMPLATES_PATH = Path(__file__).parents[1].resolve() / "templates" / "debug"


class BaseErrorMiddleware:
    def __init__(self, app: types.App, debug: bool = False) -> None:
        self.app = app
        self.debug = debug

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        response_started = False

        async def sender(message: types.Message) -> None:
            nonlocal response_started, send

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await concurrency.run(self.app, scope, receive, sender)
        except Exception as exc:
            if scope["type"] in ("http", "websocket"):
                await self.process_exception(scope, receive, send, exc, response_started)
            else:
                raise

    @abc.abstractmethod
    async def process_exception(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception, response_started: bool
    ) -> None:
        ...


class ServerErrorMiddleware(BaseErrorMiddleware):
    def _get_handler(self, scope: types.Scope) -> "Handler":
        if scope["type"] == "http":
            return self.debug_handler if self.debug else self.error_handler

        return self.noop_handler

    async def process_exception(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception, response_started: bool
    ) -> None:
        logger.exception("Unhandled exception '%s' for scope %s", exc, scope)

        handler = self._get_handler(scope)

        logger.debug("Exception handler: %s", handler)

        response = handler(scope, receive, send, exc)

        if response and concurrency.is_async(response) and not response_started:
            await response(scope, receive=receive, send=send)

        # We always continue to raise the exception.
        # This allows servers to log the error, or test clients to optionally raise the error within the test case.
        raise exc

    def debug_handler(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception
    ) -> http.Response:
        request = http.Request(scope)
        accept = request.headers.get("accept", "")

        if "text/html" in accept:
            return http._FlamaTemplateResponse(
                "debug/error_500.html", context=dataclasses.asdict(ErrorContext.build(request, exc)), status_code=500
            )
        return http.PlainTextResponse("Internal Server Error", status_code=500)

    def error_handler(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception
    ) -> http.Response:
        return http.PlainTextResponse("Internal Server Error", status_code=500)

    def noop_handler(self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception) -> None:
        ...


class ExceptionMiddleware(BaseErrorMiddleware):
    def __init__(self, app: types.App, handlers: t.Optional[t.Mapping[t.Any, "Handler"]] = None, debug: bool = False):
        super().__init__(app, debug)
        handlers = handlers or {}
        self._status_handlers: dict[int, Handler] = {
            status_code: handler for status_code, handler in handlers.items() if isinstance(status_code, int)
        }
        self._exception_handlers: dict[type[Exception], Handler] = {
            **{e: handler for e, handler in handlers.items() if inspect.isclass(e) and issubclass(e, Exception)},
            exceptions.NotFoundException: self.not_found_handler,
            exceptions.MethodNotAllowedException: self.method_not_allowed_handler,
            starlette.exceptions.HTTPException: self.http_exception_handler,
            starlette.exceptions.WebSocketException: self.websocket_exception_handler,
        }

    def add_exception_handler(
        self,
        handler: "Handler",
        status_code: t.Optional[int] = None,
        exc_class: t.Optional[type[Exception]] = None,
    ) -> None:
        if status_code is None and exc_class is None:
            raise ValueError("Status code or exception class must be defined")

        if status_code is not None:
            self._status_handlers[status_code] = handler

        if exc_class is not None:
            self._exception_handlers[exc_class] = handler

    def _get_handler(self, exc: Exception) -> "Handler":
        if isinstance(exc, starlette.exceptions.HTTPException) and exc.status_code in self._status_handlers:
            return self._status_handlers[exc.status_code]
        else:
            try:
                return next(
                    self._exception_handlers[cls] for cls in type(exc).__mro__ if cls in self._exception_handlers
                )
            except StopIteration:
                raise exc

    async def process_exception(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception, response_started: bool
    ) -> None:
        logger.debug("Handled exception '%s' for scope %s", exc, scope, exc_info=True)

        handler = self._get_handler(exc)

        logger.debug("Exception handler: %s", handler)

        if response_started:
            raise RuntimeError("Caught handled exception, but response already started.") from exc

        response = await concurrency.run(handler, scope, receive, send, exc)

        if response and concurrency.is_async(response):
            await response(scope, receive, send)

    def http_exception_handler(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.HTTPException
    ) -> http.Response:
        if exc.status_code in {204, 304}:
            return http.Response(status_code=exc.status_code, headers=exc.headers)

        request = http.Request(scope, receive=receive)
        accept = request.headers.get("accept", "")

        if self.debug and exc.status_code == 404 and "text/html" in accept:
            return http._FlamaTemplateResponse(
                template="debug/error_404.html",
                context=dataclasses.asdict(NotFoundContext.build(request, scope["app"])),
                status_code=404,
            )

        return http.APIErrorResponse(detail=exc.detail, status_code=exc.status_code, exception=exc)

    async def websocket_exception_handler(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.WebSocketException
    ) -> None:
        websocket = websockets.WebSocket(scope, receive=receive, send=send)
        await websocket.close(code=exc.code, reason=exc.reason)

    async def not_found_handler(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.NotFoundException
    ) -> t.Optional[http.Response]:
        if scope.get("type", "") == "websocket":
            await self.websocket_exception_handler(scope, receive, send, exc=exceptions.WebSocketException(1000))
            return None

        if "app" in scope:
            return self.http_exception_handler(scope, receive, send, exc=exceptions.HTTPException(status_code=404))

        return http.PlainTextResponse("Not Found", status_code=404)

    async def method_not_allowed_handler(
        self,
        scope: types.Scope,
        receive: types.Receive,
        send: types.Send,
        exc: exceptions.MethodNotAllowedException,
    ) -> t.Optional[http.Response]:
        if scope.get("type", "") == "websocket":
            await self.websocket_exception_handler(scope, receive, send, exc=exceptions.WebSocketException(1000))
            return None

        return self.http_exception_handler(
            scope,
            receive,
            send,
            exc=exceptions.HTTPException(status_code=405, headers={"Allow": ", ".join(exc.allowed)}),
        )
