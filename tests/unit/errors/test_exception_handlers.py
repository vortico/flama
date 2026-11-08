from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import exceptions, http, types
from flama.applications import Flama
from flama.errors.exception_handlers import (
    ExceptionHandler,
    HTTPExceptionHandler,
    JSONRPCExceptionHandler,
    RoutingExceptionHandler,
    WebSocketExceptionHandler,
)
from flama.http.data_structures import JSONRPCStatus
from flama.http.responses.api import APIErrorResponse
from flama.http.responses.jsonrpc import JSONRPCErrorResponse
from flama.http.responses.templates import _FlamaTemplateResponse


class _DomainError(Exception): ...


class _NotAllowed(_DomainError): ...


class _Expired(_NotAllowed): ...


class _Conflict(_DomainError): ...


class _Unhandled(_DomainError): ...


class _Handler(ExceptionHandler):
    exc_class = _DomainError

    def not_allowed(self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: _NotAllowed):
        return "not_allowed"

    async def conflict(self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: "_Conflict"):
        return "conflict"

    def unannotated(self, scope, receive, send, exc):
        return "unannotated"  # pragma: no cover

    def not_an_exception(self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: int):
        return "not_an_exception"  # pragma: no cover

    def _private(self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: _DomainError):
        return "private"  # pragma: no cover


class TestCaseExceptionHandler:
    @pytest.fixture(scope="function")
    def handler(self):
        return _Handler()

    @pytest.mark.parametrize(
        "exception", [TypeError("_Undeclared must declare the exception class it handles")], indirect=["exception"]
    )
    def test_init_subclass_undeclared(self, exception):
        with exception:

            class _Undeclared(ExceptionHandler): ...

    def test_methods(self, handler):
        assert handler._methods == {_NotAllowed: handler.not_allowed, _Conflict: handler.conflict}

    @pytest.mark.parametrize(
        "exception", [TypeError("_Outside.value_error handles ValueError, which is not a _DomainError")], indirect=True
    )
    def test_methods_outside_family(self, exception):
        class _Outside(ExceptionHandler):
            exc_class = _DomainError

            def value_error(self, scope: types.Scope, receive: types.Receive, send: types.Send, exc: ValueError): ...

        with exception:
            _ = _Outside()._methods

    @pytest.mark.parametrize(
        ["exc", "result"],
        [
            pytest.param(_NotAllowed(), True, id="handled"),
            pytest.param(_Expired(), True, id="handled_parent"),
            pytest.param(_Unhandled(), False, id="unhandled"),
            pytest.param(ValueError(), False, id="outside_family"),
        ],
    )
    def test_handles(self, handler, exc, result):
        assert handler.handles(exc) is result

    @pytest.mark.parametrize(
        ["exc", "result"],
        [
            pytest.param(_NotAllowed(), "not_allowed", id="sync"),
            pytest.param(_Conflict(), "conflict", id="async"),
            # An exception without a method of its own is answered by its closest handled parent.
            pytest.param(_Expired(), "not_allowed", id="closest_parent"),
        ],
    )
    async def test_call(self, handler, exc, result):
        assert await handler(MagicMock(), MagicMock(), MagicMock(), exc) == result

    @pytest.mark.parametrize("exception", [_Unhandled], indirect=["exception"])
    async def test_call_unhandled(self, handler, exception):
        with exception:
            await handler(MagicMock(), MagicMock(), MagicMock(), _Unhandled())


class TestCaseHTTPExceptionHandler:
    @pytest.mark.parametrize(
        ["debug", "accept", "exc", "response_class", "response_params", "patch_target"],
        (
            pytest.param(
                False,
                None,
                exceptions.HTTPException(204),
                http.PlainTextResponse,
                {"_pos": ("",), "status_code": 204, "headers": None},
                "flama.errors.exception_handlers.http.PlainTextResponse",
                id="204",
            ),
            pytest.param(
                False,
                None,
                exceptions.HTTPException(304),
                http.PlainTextResponse,
                {"_pos": ("",), "status_code": 304, "headers": None},
                "flama.errors.exception_handlers.http.PlainTextResponse",
                id="304",
            ),
            pytest.param(
                True,
                b"text/html",
                exceptions.HTTPException(404, "Foo"),
                _FlamaTemplateResponse,
                {"_pos": ("debug/error_404.html",), "context": {}, "status_code": 404, "headers": None},
                "flama.errors.exception_handlers._FlamaTemplateResponse",
                id="debug_404",
            ),
            pytest.param(
                False,
                None,
                exceptions.HTTPException(400, "Foo"),
                APIErrorResponse,
                {"detail": "Foo", "status_code": 400, "headers": None},
                "flama.errors.exception_handlers.APIErrorResponse",
                id="other",
            ),
            pytest.param(
                False,
                None,
                exceptions.HTTPException(405, "Foo", headers={"Allow": "GET"}),
                APIErrorResponse,
                {"detail": "Foo", "status_code": 405, "headers": {"Allow": "GET"}},
                "flama.errors.exception_handlers.APIErrorResponse",
                id="other_with_headers",
            ),
        ),
    )
    def test_http_exception(
        self, asgi_scope, asgi_receive, asgi_send, debug, accept, exc, response_class, response_params, patch_target
    ):
        handler = HTTPExceptionHandler(debug=debug)
        asgi_scope["type"] = "http"
        asgi_scope["app"] = MagicMock(Flama)

        if accept:
            asgi_scope["headers"].append((b"accept", accept))

        if response_class == APIErrorResponse:
            response_params["exception"] = exc

        with (
            patch(patch_target, spec=response_class) as response_mock,
            patch("flama.errors.exception_handlers.dataclasses.asdict", return_value={}),
        ):
            response = handler.http_exception(asgi_scope, asgi_receive, asgi_send, exc)

            assert isinstance(response, response_class)
            pos = response_params.pop("_pos", ())
            assert response_mock.call_args_list == [call(*pos, **response_params)]


class TestCaseJSONRPCExceptionHandler:
    def test_jsonrpc_exception(self, asgi_scope, asgi_receive, asgi_send):
        exc = exceptions.JSONRPCException(status_code=JSONRPCStatus.METHOD_NOT_FOUND, request_id=42, detail="Not found")

        response = JSONRPCExceptionHandler().jsonrpc_exception(asgi_scope, asgi_receive, asgi_send, exc)

        assert isinstance(response, JSONRPCErrorResponse)


class TestCaseWebSocketExceptionHandler:
    async def test_websocket_exception(self, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        exc = exceptions.WebSocketException(1011, "Foo reason")

        with patch.object(http.WebSocket, "close", new_callable=AsyncMock) as websocket_close_mock:
            await WebSocketExceptionHandler().websocket_exception(asgi_scope, asgi_receive, asgi_send, exc)

        assert websocket_close_mock.call_args_list == [call(code=exc.code, reason=exc.reason)]


class TestCaseRoutingExceptionHandler:
    @pytest.fixture(scope="function")
    def handler(self):
        return RoutingExceptionHandler()

    def test_init(self):
        handler = RoutingExceptionHandler(debug=True)

        assert handler._http.debug

    async def test_not_found_http(self, handler, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "http"
        asgi_scope["app"] = MagicMock(Flama)
        exc = exceptions.NotFoundException()

        with patch.object(handler._http, "http_exception") as mock:
            await handler.not_found(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [
            call(asgi_scope, asgi_receive, asgi_send, exc=exceptions.HTTPException(status_code=404))
        ]

    async def test_not_found_http_no_app(self, handler, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "http"
        del asgi_scope["app"]
        exc = exceptions.NotFoundException()

        with patch("flama.errors.exception_handlers.PlainTextResponse") as mock:
            await handler.not_found(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [call("Not Found", status_code=404)]

    async def test_not_found_websocket(self, handler, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        exc = exceptions.NotFoundException()

        with patch.object(handler._websocket, "websocket_exception") as mock:
            await handler.not_found(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [
            call(asgi_scope, asgi_receive, asgi_send, exc=exceptions.WebSocketException(1000))
        ]

    async def test_method_not_allowed_http(self, handler, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "http"
        asgi_scope["app"] = MagicMock(Flama)
        exc = exceptions.MethodNotAllowedException("/", "POST", {"GET"})

        with patch.object(handler._http, "http_exception") as mock:
            await handler.method_not_allowed(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [
            call(
                asgi_scope,
                asgi_receive,
                asgi_send,
                exc=exceptions.HTTPException(status_code=405, headers={"Allow": "GET"}),
            )
        ]

    async def test_method_not_allowed_websocket(self, handler, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        exc = exceptions.MethodNotAllowedException("/", "POST", {"GET"})

        with patch.object(handler._websocket, "websocket_exception") as mock:
            await handler.method_not_allowed(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [
            call(asgi_scope, asgi_receive, asgi_send, exc=exceptions.WebSocketException(1000))
        ]
