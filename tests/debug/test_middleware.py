from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import starlette.exceptions

from flama import exceptions, http, types, websockets
from flama.applications import Flama
from flama.debug.data_structures import ErrorContext
from flama.debug.middleware import BaseErrorMiddleware, ExceptionMiddleware, ServerErrorMiddleware


class TestCaseBaseErrorMiddleware:
    @pytest.fixture
    def middleware_cls(self):
        class FooMiddleware(BaseErrorMiddleware):
            async def process_exception(
                self,
                scope: types.Scope,
                receive: types.Receive,
                send: types.Send,
                exc: Exception,
                response_started: bool,
            ) -> None: ...

        return FooMiddleware

    def test_init(self, middleware_cls):
        app = AsyncMock()
        middleware = middleware_cls(app=app, debug=True)
        assert middleware.app == app
        assert middleware.debug

    async def test_call_http(self, middleware_cls, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "http"
        exc = ValueError()
        app = AsyncMock(side_effect=exc)
        middleware = middleware_cls(app=app, debug=True)
        with patch.object(middleware, "process_exception", new_callable=AsyncMock):
            await middleware(asgi_scope, asgi_receive, asgi_send)
            assert middleware.app.call_count == 1
            scope, receive, send = middleware.app.call_args_list[0][0]
            assert scope == asgi_scope
            assert receive == asgi_receive
            assert middleware.process_exception.call_args_list == [
                call(asgi_scope, asgi_receive, asgi_send, exc, False)
            ]

    async def test_call_websocket(self, middleware_cls, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        exc = ValueError()
        app = AsyncMock(side_effect=exc)
        middleware = middleware_cls(app=app, debug=True)
        with patch.object(middleware, "process_exception", new_callable=AsyncMock):
            await middleware(asgi_scope, asgi_receive, asgi_send)
            assert middleware.app.call_count == 1
            scope, receive, send = middleware.app.call_args_list[0][0]
            assert scope == asgi_scope
            assert receive == asgi_receive
            assert middleware.process_exception.call_args_list == [
                call(asgi_scope, asgi_receive, asgi_send, exc, False)
            ]


class TestCaseServerErrorMiddleware:
    @pytest.fixture
    def middleware(self):
        return ServerErrorMiddleware(app=AsyncMock())

    @pytest.mark.parametrize(
        ["request_type", "debug", "handler"],
        (
            pytest.param("http", True, "debug_handler", id="http_debug"),
            pytest.param("http", False, "error_handler", id="http_no_debug"),
            pytest.param("websocket", True, "noop_handler", id="websocket_debug"),
            pytest.param("websocket", False, "noop_handler", id="websocket_no_debug"),
        ),
    )
    def test_get_handler(self, middleware, asgi_scope, request_type, debug, handler):
        asgi_scope["type"] = request_type
        middleware.debug = debug

        result_handler = middleware._get_handler(asgi_scope)

        assert result_handler == getattr(middleware, handler)

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
        response_method = "debug_handler" if debug else "error_handler"
        exc = ValueError("Foo")
        with (
            patch.object(ServerErrorMiddleware, response_method, new=MagicMock(return_value=AsyncMock())) as response,
            pytest.raises(ValueError, match="Foo"),
        ):
            await middleware.process_exception(asgi_scope, asgi_receive, asgi_send, exc, response_started)

            if debug:
                assert ServerErrorMiddleware.debug_handler.call_args_list == [call(asgi_scope, exc)]
            else:
                assert ServerErrorMiddleware.error_handler.call_args_list == [call(asgi_scope, exc)]

            if response_started:
                assert response.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]
            else:
                assert response.call_args_list == []

    def test_debug_response_html(self, middleware, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["headers"].append((b"accept", b"text/html"))
        exc = ValueError()
        error_context_mock, context_mock = MagicMock(), MagicMock()
        with (
            patch("flama.debug.middleware.dataclasses.asdict", return_value=context_mock) as dataclasses_dict,
            patch.object(ErrorContext, "build", return_value=error_context_mock),
            patch.object(http._FlamaTemplateResponse, "__init__", return_value=None) as response_mock,
        ):
            response = middleware.debug_handler(asgi_scope, asgi_receive, asgi_send, exc)
            assert ErrorContext.build.call_count == 1
            assert dataclasses_dict.call_args_list == [call(error_context_mock)]
            assert isinstance(response, http._FlamaTemplateResponse)
            assert response_mock.call_args_list == [call("debug/error_500.html", context=context_mock, status_code=500)]

    def test_debug_response_text(self, middleware, asgi_scope, asgi_receive, asgi_send):
        exc = ValueError()
        with patch.object(http.PlainTextResponse, "__init__", return_value=None) as response_mock:
            response = middleware.debug_handler(asgi_scope, asgi_receive, asgi_send, exc)
            assert isinstance(response, http.PlainTextResponse)
            assert response_mock.call_args_list == [call("Internal Server Error", status_code=500)]

    def test_error_response(self, middleware, asgi_scope, asgi_receive, asgi_send):
        exc = ValueError()
        with patch.object(http.PlainTextResponse, "__init__", return_value=None) as response_mock:
            response = middleware.error_handler(asgi_scope, asgi_receive, asgi_send, exc)
            assert isinstance(response, http.PlainTextResponse)
            assert response_mock.call_args_list == [call("Internal Server Error", status_code=500)]


class TestCaseExceptionMiddleware:
    @pytest.fixture
    def middleware(self):
        return ExceptionMiddleware(app=AsyncMock())

    @pytest.fixture
    def handler(self):
        def _handler(): ...

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
            exceptions.NotFoundException: middleware.not_found_handler,
            exceptions.MethodNotAllowedException: middleware.method_not_allowed_handler,
            starlette.exceptions.HTTPException: middleware.http_exception_handler,
            starlette.exceptions.WebSocketException: middleware.websocket_exception_handler,
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
            exceptions.NotFoundException: middleware.not_found_handler,
            exceptions.MethodNotAllowedException: middleware.method_not_allowed_handler,
            starlette.exceptions.HTTPException: middleware.http_exception_handler,
            starlette.exceptions.WebSocketException: middleware.websocket_exception_handler,
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
            pytest.param(400, None, exceptions.HTTPException(400), None, id="status_code"),
            pytest.param(None, ValueError, ValueError("Foo"), None, id="exc_class"),
            pytest.param(400, ValueError, ValueError("Foo"), None, id="status_code_and_exc_class"),
            pytest.param(None, Exception, ValueError("Foo"), None, id="child_exc_class"),
            pytest.param(
                400, None, exceptions.HTTPException(401), exceptions.HTTPException(401), id="handler_not_found"
            ),
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
        response_mock = AsyncMock() if request_type == "http" else None
        with (
            exception,
            patch.object(middleware, "_get_handler", return_value=handler_mock),
            patch("flama.debug.middleware.concurrency.run", new=AsyncMock(return_value=response_mock)) as run_mock,
        ):
            await middleware.process_exception(asgi_scope, asgi_receive, asgi_send, expected_exc, response_started)

            if request_type == "http":
                assert run_mock.call_count == 1
                handler, scope, receive, send, exc = run_mock.call_args_list[0][0]
                assert handler == handler_mock
                assert scope == asgi_scope
                assert receive == asgi_receive
                assert exc == expected_exc
                assert response_mock.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

            elif request_type == "websocket":
                assert run_mock.call_count == 1
                handler, scope, receive, send, exc = run_mock.call_args_list[0][0]
                assert handler == handler_mock
                assert scope == asgi_scope
                assert receive == asgi_receive
                assert exc == expected_exc

    @pytest.mark.parametrize(
        ["debug", "accept", "exc", "response_class", "response_params"],
        (
            pytest.param(
                False,
                None,
                exceptions.HTTPException(204),
                http.Response,
                {"status_code": 204, "headers": None},
                id="204",
            ),
            pytest.param(
                False,
                None,
                exceptions.HTTPException(304),
                http.Response,
                {"status_code": 304, "headers": None},
                id="304",
            ),
            pytest.param(
                True,
                b"text/html",
                exceptions.HTTPException(404, "Foo"),
                http._FlamaTemplateResponse,
                {"template": "debug/error_404.html", "context": {}, "status_code": 404},
                id="debug_404",
            ),
            pytest.param(
                False,
                None,
                exceptions.HTTPException(400, "Foo"),
                http.APIErrorResponse,
                {"detail": "Foo", "status_code": 400},
                id="other",
            ),
        ),
    )
    def test_http_exception_handler(
        self, middleware, asgi_scope, asgi_receive, asgi_send, debug, accept, exc, response_class, response_params
    ):
        asgi_scope["type"] = "http"
        asgi_scope["app"] = MagicMock(Flama)
        middleware.debug = debug

        if accept:
            asgi_scope["headers"].append((b"accept", accept))

        if response_class == http.APIErrorResponse:
            response_params["exception"] = exc

        with (
            patch(f"flama.debug.middleware.http.{response_class.__name__}", spec=response_class) as response_mock,
            patch("flama.debug.middleware.dataclasses.asdict", return_value={}),
        ):
            response = middleware.http_exception_handler(asgi_scope, asgi_receive, asgi_send, exc)

            assert isinstance(response, response_class)
            assert response_mock.call_args_list == [call(**response_params)]

    async def test_websocket_exception_handler(self, middleware, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        exc = exceptions.WebSocketException(1011, "Foo reason")

        with patch.object(websockets.WebSocket, "close", new_callable=AsyncMock) as websocket_close_mock:
            await middleware.websocket_exception_handler(asgi_scope, asgi_receive, asgi_send, exc)

            assert websocket_close_mock.call_args_list == [call(code=exc.code, reason=exc.reason)]

    async def test_not_found_handler_http(self, middleware, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "http"
        asgi_scope["app"] = MagicMock(Flama)
        exc = exceptions.NotFoundException()

        with patch("flama.debug.middleware.ExceptionMiddleware.http_exception_handler") as mock:
            await middleware.not_found_handler(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [
            call(asgi_scope, asgi_receive, asgi_send, exc=exceptions.HTTPException(status_code=404))
        ]

    async def test_not_found_handler_http_no_app(self, middleware, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "http"
        del asgi_scope["app"]
        exc = exceptions.NotFoundException()

        with patch("flama.debug.middleware.http.PlainTextResponse") as mock:
            await middleware.not_found_handler(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [call("Not Found", status_code=404)]

    async def test_not_found_handler_websocket(self, middleware, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        exc = exceptions.NotFoundException()

        with patch("flama.debug.middleware.ExceptionMiddleware.websocket_exception_handler") as mock:
            await middleware.not_found_handler(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [
            call(asgi_scope, asgi_receive, asgi_send, exc=exceptions.WebSocketException(1000))
        ]

    async def test_method_not_allowed_handler_http(self, middleware, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "http"
        asgi_scope["app"] = MagicMock(Flama)
        exc = exceptions.MethodNotAllowedException("/", "POST", {"GET"})

        with patch("flama.debug.middleware.ExceptionMiddleware.http_exception_handler") as mock:
            await middleware.method_not_allowed_handler(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [
            call(
                asgi_scope,
                asgi_receive,
                asgi_send,
                exc=exceptions.HTTPException(status_code=405, headers={"Allow": "GET"}),
            )
        ]

    async def test_method_not_allowed_handler_websocket(self, middleware, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        exc = exceptions.MethodNotAllowedException("/", "POST", {"GET"})

        with patch("flama.debug.middleware.ExceptionMiddleware.websocket_exception_handler") as mock:
            await middleware.method_not_allowed_handler(asgi_scope, asgi_receive, asgi_send, exc)

        assert mock.call_args_list == [
            call(asgi_scope, asgi_receive, asgi_send, exc=exceptions.WebSocketException(1000))
        ]
