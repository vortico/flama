import dataclasses
import functools
import inspect
import typing as t

from flama import _concurrency, exceptions, http, types
from flama.errors.data_structures import NotFoundContext
from flama.http.responses.api import APIErrorResponse
from flama.http.responses.jsonrpc import JSONRPCErrorResponse
from flama.http.responses.plain_text import PlainTextResponse
from flama.http.responses.templates import _FlamaTemplateResponse

__all__ = [
    "ExceptionHandler",
    "HTTPExceptionHandler",
    "JSONRPCExceptionHandler",
    "WebSocketExceptionHandler",
    "RoutingExceptionHandler",
]


class ExceptionHandler:
    """Exception handler answering a family of exceptions, with a method for each exception it handles.

    The family is the exception class the handler declares in ``exc_class``, which is the class it is registered for.
    A public method handles the exception type its last parameter is annotated with, which must belong to the family,
    and takes the arguments of any exception handler. An exception is answered by the method for its closest handled
    parent, and one without any is raised again.
    """

    exc_class: t.ClassVar[type[Exception]]

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)

        if not (inspect.isclass(exc_class := getattr(cls, "exc_class", None)) and issubclass(exc_class, Exception)):
            raise TypeError(f"{cls.__name__} must declare the exception class it handles as 'exc_class'")

    async def __call__(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: Exception
    ) -> "http.Response | None":
        if (method := self._method(exc)) is None:
            raise exc

        return await _concurrency.run(method, scope, receive, send, exc)

    def handles(self, exc: Exception) -> bool:
        """Whether a method answers the exception, or one of its parents.

        :param exc: Exception to answer.
        :return: True if the exception is answered.
        """
        return isinstance(exc, self.exc_class) and self._method(exc) is not None

    def _method(self, exc: Exception) -> t.Callable[..., t.Any] | None:
        return next((self._methods[cls] for cls in type(exc).__mro__ if cls in self._methods), None)

    @functools.cached_property
    def _methods(self) -> dict[type, t.Callable[..., t.Any]]:
        """The method answering each exception type handled.

        :return: Methods by the exception type they handle.
        :raises TypeError: If a method handles an exception outside the family.
        """
        methods = {}
        for name, function in inspect.getmembers(type(self), inspect.isfunction):
            # The base class's own methods take an exception too, but answer none.
            if (
                name.startswith("_")
                or name in vars(ExceptionHandler)
                or not (parameters := list(inspect.signature(function).parameters))
            ):
                continue

            exc_type = t.get_type_hints(function).get(parameters[-1])
            if inspect.isclass(exc_type) and issubclass(exc_type, Exception):
                if not issubclass(exc_type, self.exc_class):
                    raise TypeError(
                        f"{type(self).__name__}.{name} handles {exc_type.__name__}, "
                        f"which is not a {self.exc_class.__name__}"
                    )
                methods[exc_type] = getattr(self, name)

        return methods


class HTTPExceptionHandler(ExceptionHandler):
    """Answer an HTTP exception with an error response carrying its status.

    :param debug: Whether to render the debug page for a missing resource requested from a browser.
    """

    exc_class = exceptions.HTTPException

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug

    def http_exception(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.HTTPException
    ) -> http.Response:
        if exc.status_code in {204, 304}:
            return http.PlainTextResponse("", status_code=exc.status_code, headers=exc.headers)

        request = http.Request(scope, receive=receive)
        accept = request.headers.get("accept", "")

        if self.debug and exc.status_code == 404 and "text/html" in accept:
            return _FlamaTemplateResponse(
                "debug/error_404.html",
                context=dataclasses.asdict(NotFoundContext.build(request, scope["app"])),
                status_code=404,
                headers=exc.headers,
            )

        return APIErrorResponse(detail=exc.detail, status_code=exc.status_code, exception=exc, headers=exc.headers)


class JSONRPCExceptionHandler(ExceptionHandler):
    """Answer a JSON-RPC exception with an error envelope carrying its code."""

    exc_class = exceptions.JSONRPCException

    def jsonrpc_exception(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.JSONRPCException
    ) -> JSONRPCErrorResponse:
        return JSONRPCErrorResponse(status_code=exc.status_code, message=exc.detail, id=exc.request_id, data=exc.data)


class WebSocketExceptionHandler(ExceptionHandler):
    """Answer a WebSocket exception by closing the connection with its code and reason."""

    exc_class = exceptions.WebSocketException

    async def websocket_exception(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.WebSocketException
    ) -> None:
        websocket = http.WebSocket(scope, receive=receive, send=send)
        await websocket.close(code=exc.code, reason=exc.reason)


class RoutingExceptionHandler(ExceptionHandler):
    """Answer a request that cannot be routed, as HTTP or WebSocket depending on the request.

    No endpoint is reached yet, so the answer is the one of the request's protocol.

    :param debug: Whether to render the debug page for a missing resource requested from a browser.
    """

    exc_class = exceptions.RoutingException

    def __init__(self, debug: bool = False) -> None:
        self._http = HTTPExceptionHandler(debug=debug)
        self._websocket = WebSocketExceptionHandler()

    async def not_found(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.NotFoundException
    ) -> http.Response | None:
        if scope.get("type", "") == "websocket":
            await self._websocket.websocket_exception(scope, receive, send, exc=exceptions.WebSocketException(1000))
            return None

        if "app" in scope:
            return self._http.http_exception(scope, receive, send, exc=exceptions.HTTPException(status_code=404))

        return PlainTextResponse("Not Found", status_code=404)

    async def method_not_allowed(
        self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: exceptions.MethodNotAllowedException
    ) -> http.Response | None:
        if scope.get("type", "") == "websocket":
            await self._websocket.websocket_exception(scope, receive, send, exc=exceptions.WebSocketException(1000))
            return None

        return self._http.http_exception(
            scope,
            receive,
            send,
            exc=exceptions.HTTPException(status_code=405, headers={"Allow": ", ".join(exc.allowed)}),
        )
