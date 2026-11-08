import abc
import dataclasses
import inspect
import logging
import typing as t

from flama import _concurrency, exceptions, http, types
from flama.errors.data_structures import ErrorContext
from flama.errors.exception_handlers import ExceptionHandler
from flama.http.responses.plain_text import PlainTextResponse
from flama.http.responses.templates import _FlamaTemplateResponse
from flama.middleware import Middleware

if t.TYPE_CHECKING:
    from flama.errors.types import ExceptionHandlerFunction

logger = logging.getLogger(__name__)

__all__ = ["ServerErrorMiddleware", "ExceptionMiddleware"]


class BaseErrorMiddleware(Middleware):
    def __init__(self, debug: bool = False) -> None:
        self.debug = debug

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        response_started = False

        async def sender(message: types.Message) -> None:
            nonlocal response_started, send

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await _concurrency.run(self.app, scope, receive, sender)
        except Exception as exc:
            if scope["type"] in ("http", "websocket"):
                await self.process_exception(scope, receive, send, exc, response_started)
            else:
                raise

    @abc.abstractmethod
    async def process_exception(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception, response_started: bool
    ) -> None: ...


class ServerErrorMiddleware(BaseErrorMiddleware):
    def _get_handler(self, scope: types.Scope) -> "ExceptionHandlerFunction":
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

        if response and _concurrency.is_async(response) and not response_started:
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
            return _FlamaTemplateResponse(
                "debug/error_500.html", context=dataclasses.asdict(ErrorContext.build(request, exc)), status_code=500
            )
        return PlainTextResponse("Internal Server Error", status_code=500)

    def error_handler(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception
    ) -> http.Response:
        return PlainTextResponse("Internal Server Error", status_code=500)

    def noop_handler(self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception) -> None: ...


class ExceptionMiddleware(BaseErrorMiddleware):
    """Handle the exceptions raised further down the stack that a handler is registered for.

    An exception is handled by the handler registered for its closest class, skipping an :class:`ExceptionHandler`
    that does not answer it. Any other exception is left to the middleware above.

    :param handlers: Handlers by HTTP status code or exception type.
    :param debug: Whether to render debug responses.
    """

    def __init__(
        self, handlers: t.Mapping[int | type[Exception], "ExceptionHandlerFunction"] | None = None, debug: bool = False
    ) -> None:
        super().__init__(debug)
        handlers = handlers or {}
        self._status_handlers: dict[int, ExceptionHandlerFunction] = {
            status_code: handler for status_code, handler in handlers.items() if isinstance(status_code, int)
        }
        self._exception_handlers: dict[type[Exception], ExceptionHandlerFunction] = {
            e: handler for e, handler in handlers.items() if inspect.isclass(e) and issubclass(e, Exception)
        }

    def add_exception_handler(
        self,
        handler: "ExceptionHandlerFunction",
        status_code: int | None = None,
        exc_class: type[Exception] | None = None,
    ) -> None:
        if status_code is None and exc_class is None:
            raise ValueError("Status code or exception class must be defined")

        if status_code is not None:
            self._status_handlers[status_code] = handler

        if exc_class is not None:
            self._exception_handlers[exc_class] = handler

    def _get_handler(self, exc: Exception) -> "ExceptionHandlerFunction":
        if isinstance(exc, exceptions.HTTPException) and exc.status_code in self._status_handlers:
            return self._status_handlers[exc.status_code]

        for cls in type(exc).__mro__:
            handler = self._exception_handlers.get(t.cast(type[Exception], cls))
            if handler is not None and (not isinstance(handler, ExceptionHandler) or handler.handles(exc)):
                return handler

        raise exc

    async def process_exception(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception, response_started: bool
    ) -> None:
        logger.debug("Handled exception '%s' for scope %s", exc, scope, exc_info=True)

        handler = self._get_handler(exc)

        logger.debug("Exception handler: %s", handler)

        if response_started:
            raise RuntimeError("Caught handled exception, but response already started.") from exc

        response = await _concurrency.run(handler, scope, receive, send, exc)

        if response and _concurrency.is_async(response):
            await response(scope, receive, send)
