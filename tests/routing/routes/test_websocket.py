import functools
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import Flama, endpoints, exceptions, types, websockets
from flama.endpoints import WebSocketEndpoint
from flama.injection.injector import Injector
from flama.routing.router import Router
from flama.routing.routes.base import BaseRoute
from flama.routing.routes.websocket import WebSocketEndpointWrapper, WebSocketFunctionWrapper, WebSocketRoute


class TestCaseWebsocketFunctionWrapper:
    @pytest.fixture(scope="function")
    def app(self):
        return MagicMock(
            spec=Flama,
            router=MagicMock(spec=Router, resolve_route=MagicMock(side_effect=lambda x: (AsyncMock(), x))),
            injector=MagicMock(
                spec=Injector,
                inject=AsyncMock(side_effect=lambda x, y: functools.partial(x, y["websocket"], y["websocket_message"])),
            ),
        )

    @pytest.fixture(scope="function")
    def endpoint(self):
        async def foo(websocket: websockets.WebSocket, data: types.Data):
            await websocket.send_json({"foo": "bar"})

        return WebSocketFunctionWrapper(foo)

    @pytest.fixture(scope="function")
    def websocket(self):
        return MagicMock(spec=websockets.WebSocket)

    async def test_call(self, app, endpoint, websocket):
        scope, receive, send = (
            types.Scope({"app": app, "path": "/", "root_app": app, "type": "websocket", "websocket": websocket}),
            AsyncMock(),
            AsyncMock(),
        )

        with patch("flama.websockets.WebSocket", return_value=websocket):
            await endpoint(scope, receive, send)

            assert websocket.send_json.call_args_list == [call({"foo": "bar"})]


class TestCaseWebsocketEndpointWrapper:
    @pytest.fixture(scope="function")
    def app(self):
        return MagicMock(
            spec=Flama,
            router=MagicMock(spec=Router, resolve_route=MagicMock(side_effect=lambda x: (AsyncMock(), x))),
            injector=MagicMock(
                spec=Injector,
                inject=AsyncMock(side_effect=lambda x, y: functools.partial(x, y["websocket"], y["websocket_message"])),
            ),
        )

    @pytest.fixture(scope="function")
    def endpoint(self):
        class Endpoint(endpoints.WebSocketEndpoint):
            async def on_receive(self, websocket: websockets.WebSocket, data: types.Data) -> None:
                await websocket.send_json({"foo": "bar"})

        return WebSocketEndpointWrapper(Endpoint)

    @pytest.fixture(scope="function")
    def websocket(self):
        return MagicMock(spec=websockets.WebSocket)

    async def test_call(self, app, endpoint, websocket):
        scope, receive, send = (
            types.Scope({"app": app, "path": "/", "root_app": app, "type": "websocket", "websocket": websocket}),
            AsyncMock(),
            AsyncMock(),
        )

        websocket.is_connected = False
        websocket.receive = AsyncMock(return_value={})
        with patch("flama.websockets.WebSocket", return_value=websocket):
            await endpoint(scope, receive, send)


class TestCaseWebsocketRoute:
    @pytest.fixture(scope="function")
    def route(self):
        return WebSocketRoute("/", lambda: None, name="foo", include_in_schema=False)

    @pytest.fixture(scope="function")
    def endpoint(self, request):
        if request.param == "function":

            def foo(): ...

            return foo

        elif request.param == "endpoint":

            class FooEndpoint(WebSocketEndpoint):
                async def on_receive(self, websocket: websockets.WebSocket, data: types.Data) -> None:
                    await websocket.send_text("foo")

            return FooEndpoint

    @pytest.mark.parametrize(
        ["endpoint", "name", "wrapper", "exception"],
        (
            pytest.param("function", "foo", WebSocketFunctionWrapper, None, id="function"),
            pytest.param("endpoint", "FooEndpoint", WebSocketEndpointWrapper, None, id="endpoint"),
            pytest.param(
                None,
                None,
                None,
                exceptions.ApplicationError("Endpoint must be a callable or a WebSocketEndpoint subclass"),
                id="error_handler",
            ),
        ),
        indirect=["endpoint", "exception"],
    )
    def test_init(self, endpoint, name, wrapper, exception):
        with exception:
            route = WebSocketRoute("/", endpoint, include_in_schema=False)

            assert route.path == "/"
            assert isinstance(route.app, wrapper)
            assert route.endpoint == endpoint
            assert route.name == name
            assert route.include_in_schema is False

    @pytest.mark.parametrize(
        ["scope_type", "handle_call"],
        (
            pytest.param("websocket", True, id="websocket"),
            pytest.param("wrong", False, id="wrong"),
        ),
    )
    async def test_call(self, route, asgi_scope, asgi_receive, asgi_send, scope_type, handle_call):
        scope = types.Scope({**asgi_scope, "type": scope_type})
        route_scope = types.Scope({"foo": "bar"})
        handle = AsyncMock()
        expected_calls = [call(types.Scope({**scope, **route_scope}), asgi_receive, asgi_send)] if handle_call else []

        with patch.object(route, "handle", new=handle), patch.object(route, "route_scope", return_value=route_scope):
            await route(scope, asgi_receive, asgi_send)

        assert handle.call_args_list == expected_calls

    def test_eq(self):
        def foo(): ...

        assert WebSocketRoute("/", foo, name="foo") == WebSocketRoute("/", foo, name="foo")
        assert WebSocketRoute("/", foo, name="foo") != WebSocketRoute("/", foo, name="bar")

    @pytest.mark.parametrize(
        ["endpoint", "result"],
        (
            pytest.param("function", False, id="function"),
            pytest.param("endpoint", True, id="endpoint"),
        ),
        indirect=["endpoint"],
    )
    def test_is_endpoint(self, endpoint, result):
        assert WebSocketRoute.is_endpoint(endpoint) is result

    @pytest.mark.parametrize(
        ["endpoint", "expected_handlers"],
        (
            pytest.param("function", {"WEBSOCKET"}, id="function"),
            pytest.param("endpoint", {"WEBSOCKET_CONNECT", "WEBSOCKET_RECEIVE", "WEBSOCKET_DISCONNECT"}, id="endpoint"),
        ),
        indirect=["endpoint"],
    )
    def test_endpoint_handlers(self, endpoint, expected_handlers):
        result = {x: getattr(endpoint, x.lower().replace("websocket", "on"), endpoint) for x in expected_handlers}

        route = WebSocketRoute("/", endpoint)

        assert route.endpoint_handlers() == result

    @pytest.mark.parametrize(
        ["scope_type", "path_match_return", "result"],
        (
            pytest.param("websocket", BaseRoute.Match.full, BaseRoute.Match.full, id="match"),
            pytest.param("websocket", BaseRoute.Match.none, BaseRoute.Match.none, id="no_match"),
            pytest.param("http", None, BaseRoute.Match.none, id="wrong_scope_type"),
        ),
    )
    def test_match(self, scope_type, path_match_return, result, asgi_scope):
        def foo(): ...

        route = WebSocketRoute("/", foo)

        asgi_scope["type"] = scope_type

        with patch.object(BaseRoute, "match", return_value=path_match_return):
            assert route.match(asgi_scope) == result
