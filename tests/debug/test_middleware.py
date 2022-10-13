from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama.asgi import Receive, Scope, Send
from flama.debug.middleware import BaseErrorMiddleware, ExceptionMiddleware, ServerErrorMiddleware
from flama.debug.types import ErrorContext
from flama.exceptions import HTTPException, WebSocketException
from flama.http import Request
from flama.responses import APIErrorResponse, HTMLTemplateResponse, PlainTextResponse, Response
from flama.websockets import WebSocket


class TestCaseBaseErrorMiddleware:
    @pytest.fixture
    def middleware_cls(self):
        class FooMiddleware(BaseErrorMiddleware):
            async def process_exception(
                self, scope: Scope, receive: Receive, send: Send, exc: Exception, response_started: bool
            ) -> None:
                ...

        return FooMiddleware

    def test_init(self, middleware_cls):
        app = AsyncMock()
        middleware = middleware_cls(app=app, debug=True)
        assert middleware.app == app
        assert middleware.debug

    async def test_call_http(self, middleware_cls, asgi_scope, asgi_receive, asgi_send):
        exc = ValueError()
        app = AsyncMock(side_effect=exc)
        middleware = middleware_cls(app=app, debug=True)
        with patch.object(middleware, "process_exception", new_callable=AsyncMock):
            await middleware(asgi_scope, asgi_receive, asgi_send)
            assert middleware.app.call_count == 1
            assert middleware.process_exception.call_args_list == [
                call(asgi_scope, asgi_receive, asgi_send, exc, False)
            ]

    async def test_call_websocket(self, middleware_cls, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        app = AsyncMock()
        middleware = middleware_cls(app=app, debug=True)
        with patch.object(middleware, "process_exception", new_callable=AsyncMock):
            await middleware(asgi_scope, asgi_receive, asgi_send)
            assert middleware.app.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]
            assert middleware.process_exception.call_args_list == []


class TestCaseServerErrorMiddleware:
    @pytest.fixture
    def middleware(self):
        return ServerErrorMiddleware(app=AsyncMock())

    @pytest.mark.parametrize(
        ["debug"],
        (
            pytest.param(True, id="debug"),
            pytest.param(False, id="no_debug"),
        ),
    )
    def test_get_handler(self, middleware, debug):
        middleware.debug = debug
        handler = middleware.debug_response if debug else middleware.error_response

        result_handler = middleware._get_handler()

        assert result_handler == handler

    @pytest.mark.parametrize(
        ["debug", "response_started"],
        (
            pytest.param(True, False, id="debug_not_started"),
            pytest.param(True, True, id="debug_started"),
            pytest.param(False, False, id="error_not_started"),
            pytest.param(False, True, id="error_started"),
        ),
    )
    async def test_process_exception(self, middleware, asgi_scope, asgi_receive, asgi_send, debug, response_started):
        middleware.debug = debug
        response_method = "debug_response" if debug else "error_response"
        exc = ValueError("Foo")
        with patch.object(
            ServerErrorMiddleware, response_method, new=MagicMock(return_value=AsyncMock())
        ) as response, pytest.raises(ValueError, match="Foo"):
            await middleware.process_exception(asgi_scope, asgi_receive, asgi_send, exc, response_started)

            if debug:
                assert ServerErrorMiddleware.debug_response.call_args_list == [call(Request(asgi_scope), exc)]
            else:
                assert ServerErrorMiddleware.error_response.call_args_list == [call(Request(asgi_scope), exc)]

            if response_started:
                assert response.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]
            else:
                assert response.call_args_list == []

    def test_debug_response_html(self, middleware, asgi_scope):
        asgi_scope["headers"].append((b"accept", b"text/html"))
        request = Request(asgi_scope)
        exc = ValueError()
        error_context_mock, context_mock = MagicMock(), MagicMock()
        with patch(
            "flama.debug.middleware.dataclasses.asdict", return_value=context_mock
        ) as dataclasses_dict, patch.object(ErrorContext, "build", return_value=error_context_mock), patch.object(
            HTMLTemplateResponse, "__init__", return_value=None
        ):
            response = middleware.debug_response(request, exc)
            assert ErrorContext.build.call_args_list == [call(request, exc)]
            assert dataclasses_dict.call_args_list == [call(error_context_mock)]
            assert isinstance(response, HTMLTemplateResponse)
            assert HTMLTemplateResponse.__init__.call_args_list == [call("debug/error_500.html", context=context_mock)]

    def test_debug_response_text(self, middleware, asgi_scope):
        request = Request(asgi_scope)
        exc = ValueError()
        with patch.object(PlainTextResponse, "__init__", return_value=None):
            response = middleware.debug_response(request, exc)
            assert isinstance(response, PlainTextResponse)
            assert PlainTextResponse.__init__.call_args_list == [call("Internal Server Error", status_code=500)]

    def test_error_response(self, middleware, asgi_scope):
        request = Request(asgi_scope)
        exc = ValueError()
        with patch.object(PlainTextResponse, "__init__", return_value=None):
            response = middleware.error_response(request, exc)
            assert isinstance(response, PlainTextResponse)
            assert PlainTextResponse.__init__.call_args_list == [call("Internal Server Error", status_code=500)]


class TestCaseExceptionMiddleware:
    @pytest.fixture
    def middleware(self):
        return ExceptionMiddleware(app=AsyncMock())

    @pytest.fixture
    def handler(self):
        def _handler():
            ...

        return _handler

    def test_init(self, handler):
        app = AsyncMock()
        debug = True

        middleware = ExceptionMiddleware(app=app, handlers={400: handler, ValueError: handler}, debug=debug)

        assert middleware.app == app
        assert middleware.debug == debug
        assert middleware._status_handlers == {400: handler}
        assert middleware._exception_handlers == {
            ValueError: handler,
            HTTPException: middleware.http_exception,
            WebSocketException: middleware.websocket_exception,
        }

    @pytest.mark.parametrize(
        ["status_code", "exc_class", "exception"],
        (
            pytest.param(400, None, None, id="status_code"),
            pytest.param(None, ValueError, None, id="exc_class"),
            pytest.param(400, ValueError, None, id="status_code_and_exc_class"),
            pytest.param(None, None, ValueError("Status code or exception class must be defined"), id="no_key"),
        ),
        indirect=["exception"],
    )
    def test_add_exception_handler(self, middleware, handler, status_code, exc_class, exception):
        status_code_handlers = {}
        if status_code is not None:
            status_code_handlers[status_code] = handler
        exc_class_handlers = {
            HTTPException: middleware.http_exception,
            WebSocketException: middleware.websocket_exception,
        }
        if exc_class is not None:
            exc_class_handlers[exc_class] = handler

        with exception:
            middleware.add_exception_handler(handler, status_code=status_code, exc_class=exc_class)

        assert middleware._status_handlers == status_code_handlers
        assert middleware._exception_handlers == exc_class_handlers

    @pytest.mark.parametrize(
        ["status_code", "exc_class", "key", "exception"],
        (
            pytest.param(400, None, HTTPException(400), None, id="status_code"),
            pytest.param(None, ValueError, ValueError("Foo"), None, id="exc_class"),
            pytest.param(400, ValueError, ValueError("Foo"), None, id="status_code_and_exc_class"),
            pytest.param(None, Exception, ValueError("Foo"), None, id="child_exc_class"),
            pytest.param(400, None, HTTPException(401), HTTPException(401), id="handler_not_found"),
        ),
        indirect=["exception"],
    )
    def test_get_handler(self, middleware, handler, status_code, exc_class, key, exception):
        # Force clean all handlers
        middleware._status_handlers = {}
        middleware._exception_handlers = {}
        middleware.add_exception_handler(handler=handler, status_code=status_code, exc_class=exc_class)

        with exception:
            result_handler = middleware._get_handler(key)
            if not exception:
                assert result_handler == handler

    @pytest.mark.parametrize(
        ["request_type", "response_started", "exception"],
        (
            pytest.param("http", False, None, id="http"),
            pytest.param("websocket", False, None, id="websocket"),
            pytest.param(
                None,
                True,
                RuntimeError("Caught handled exception, but response already started."),
                id="response_started_error",
            ),
        ),
        indirect=["exception"],
    )
    async def test_process_exception(
        self, middleware, asgi_scope, asgi_receive, asgi_send, request_type, response_started, exception
    ):
        expected_exc = ValueError()
        asgi_scope["type"] = request_type
        handler_mock = MagicMock()
        response_mock = AsyncMock()
        with exception, patch.object(middleware, "_get_handler", return_value=handler_mock), patch(
            "flama.debug.middleware.concurrency.run", new=AsyncMock(return_value=response_mock)
        ) as run_mock:
            await middleware.process_exception(asgi_scope, asgi_receive, asgi_send, expected_exc, response_started)

            if request_type == "http":
                assert run_mock.call_count == 1
                handler, request, exc = run_mock.call_args_list[0][0]
                assert handler == handler_mock
                assert isinstance(request, Request)
                assert request.scope == asgi_scope
                assert exc == expected_exc
                assert response_mock.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

            elif request_type == "websocket":
                assert run_mock.call_count == 1
                handler, websocket, exc = run_mock.call_args_list[0][0]
                assert handler == handler_mock
                assert isinstance(websocket, WebSocket)
                assert websocket.scope == asgi_scope
                assert exc == expected_exc

    @pytest.mark.parametrize(
        ["debug", "accept", "exc", "response_class", "response_params"],
        (
            pytest.param(False, None, HTTPException(204), Response, {"status_code": 204, "headers": None}, id="204"),
            pytest.param(False, None, HTTPException(304), Response, {"status_code": 304, "headers": None}, id="304"),
            pytest.param(
                True,
                b"text/html",
                HTTPException(404, "Foo"),
                PlainTextResponse,
                {"content": "Foo", "status_code": 404},
                id="debug_404",
            ),
            pytest.param(
                False,
                None,
                HTTPException(400, "Foo"),
                APIErrorResponse,
                {"detail": "Foo", "status_code": 400},
                id="other",
            ),
        ),
    )
    def test_http_exception(self, middleware, asgi_scope, debug, accept, exc, response_class, response_params):
        middleware.debug = debug

        if accept:
            asgi_scope["headers"].append((b"accept", accept))

        if response_class == APIErrorResponse:
            response_params["exception"] = exc

        request = Request(asgi_scope)
        with patch.object(response_class, "__init__", return_value=None):
            middleware.http_exception(request, exc)

            assert response_class.__init__.call_args_list == [call(**response_params)]

    async def test_websocket_exception(self, middleware):
        websocket = AsyncMock()
        exc = WebSocketException(1011, "Foo reason")

        await middleware.websocket_exception(websocket, exc)

        assert websocket.close.call_args_list == [call(code=exc.code, reason=exc.reason)]
