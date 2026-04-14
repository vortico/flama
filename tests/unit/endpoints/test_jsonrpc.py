import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from flama import Flama, endpoints, exceptions
from flama.http.data_structures import JSONRPCStatus


class TestCaseJSONRPCEndpoint:
    @pytest.fixture(scope="class")
    def app(self, app):
        return Flama(schema=None, docs=None)

    @pytest.fixture
    def route(self):
        return MagicMock()

    @pytest.fixture
    def endpoint_cls(self):
        class MyRPC(endpoints.JSONRPCEndpoint):
            handlers = {"add": "do_add", "fail": "do_fail"}

            def do_add(self, a: int = 0, b: int = 0):
                return a + b

            def do_fail(self):
                raise RuntimeError("boom")

        return MyRPC

    @pytest.fixture
    def endpoint(self, app, route, endpoint_cls, asgi_scope, asgi_receive, asgi_send):
        app.router = MagicMock(resolve_route=MagicMock(side_effect=lambda x: (route, x)))
        asgi_scope["app"] = app
        asgi_scope["root_app"] = app
        asgi_scope["type"] = "http"
        asgi_scope["method"] = "POST"
        asgi_scope["path"] = "/rpc"
        asgi_scope["path_params"] = {}
        asgi_scope["endpoint"] = endpoint_cls
        asgi_scope["route"] = route
        return endpoint_cls(asgi_scope, asgi_receive, asgi_send)

    def test_init_wrong_scope(self, app, route, asgi_scope, asgi_receive, asgi_send):
        class Dummy(endpoints.JSONRPCEndpoint):
            handlers = {}

        app.router = MagicMock(resolve_route=MagicMock(side_effect=lambda x: (route, x)))
        asgi_scope["type"] = "websocket"
        asgi_scope["app"] = app
        asgi_scope["root_app"] = app

        with pytest.raises(ValueError, match="Wrong scope"):
            Dummy(asgi_scope, asgi_receive, asgi_send)

    def test_init(self, endpoint):
        assert endpoint.state.request is not None

    @pytest.mark.parametrize(
        ["method", "exception"],
        [
            pytest.param("add", None, id="valid"),
            pytest.param(
                "dispatch", exceptions.JSONRPCException(status_code=JSONRPCStatus.METHOD_NOT_FOUND), id="dispatch"
            ),
            pytest.param(
                "unknown", exceptions.JSONRPCException(status_code=JSONRPCStatus.METHOD_NOT_FOUND), id="unknown"
            ),
        ],
        indirect=["exception"],
    )
    def test_handler(self, endpoint, method, exception):
        with exception:
            h = endpoint.handler(method)
            assert callable(h)

    def test_handler_not_callable(self, endpoint):
        endpoint.handlers["broken"] = "nonexistent_method"

        with pytest.raises(exceptions.JSONRPCException):
            endpoint.handler("broken")

    @pytest.mark.parametrize(
        ["body", "expected_status", "exception"],
        [
            pytest.param(
                {"jsonrpc": "2.0", "method": "add", "params": {"a": 1, "b": 2}, "id": 1},
                200,
                None,
                id="success_with_id",
            ),
            pytest.param(
                {"jsonrpc": "2.0", "method": "add", "params": {"a": 1, "b": 2}},
                202,
                None,
                id="notification",
            ),
            pytest.param(
                {"jsonrpc": "1.0", "method": "add", "id": 1},
                None,
                exceptions.JSONRPCException(status_code=JSONRPCStatus.INVALID_REQUEST),
                id="wrong_version",
            ),
            pytest.param(
                {"jsonrpc": "2.0", "id": 1},
                None,
                exceptions.JSONRPCException(status_code=JSONRPCStatus.INVALID_REQUEST),
                id="no_method",
            ),
            pytest.param(
                {"jsonrpc": "2.0", "method": "fail", "id": 1},
                None,
                exceptions.JSONRPCException(status_code=JSONRPCStatus.INTERNAL_ERROR, detail="boom"),
                id="handler_raises",
            ),
        ],
        indirect=["exception"],
    )
    async def test_dispatch(self, endpoint, body, expected_status, exception):
        endpoint.state.request = MagicMock()
        endpoint.state.request.json = AsyncMock(return_value=body)

        with exception:
            response = await endpoint.dispatch()
            assert response.status_code == expected_status

    async def test_dispatch_parse_error(self, endpoint):
        endpoint.state.request = MagicMock()
        endpoint.state.request.json = AsyncMock(side_effect=json.JSONDecodeError("bad", "", 0))

        with pytest.raises(exceptions.JSONRPCException) as exc_info:
            await endpoint.dispatch()

        assert exc_info.value.status_code == JSONRPCStatus.PARSE_ERROR

    async def test_dispatch_method_not_found_sets_request_id(self, endpoint):
        endpoint.state.request = MagicMock()
        endpoint.state.request.json = AsyncMock(return_value={"jsonrpc": "2.0", "method": "nonexistent", "id": 42})

        with pytest.raises(exceptions.JSONRPCException) as exc_info:
            await endpoint.dispatch()

        assert exc_info.value.status_code == JSONRPCStatus.METHOD_NOT_FOUND
        assert exc_info.value.request_id == 42
