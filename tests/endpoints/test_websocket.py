from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import pytest
import starlette.websockets

from flama import Component, Flama, endpoints, exceptions, types, websockets


class Puppy:
    name = "Canna"


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


class TestCaseWebSocketEndpoint:
    @pytest.fixture(scope="class")
    def app(self, app):
        return Flama(schema=None, docs=None, components=[PuppyComponent()])

    @pytest.fixture
    def endpoint(self, app, asgi_scope, asgi_receive, asgi_send):
        @app.websocket_route("/")
        class FooEndpoint(endpoints.WebSocketEndpoint):
            def get(self): ...

        asgi_scope["app"] = app
        asgi_scope["root_app"] = app
        asgi_scope["type"] = "websocket"
        with patch("flama.websockets.WebSocket", spec=websockets.WebSocket):
            return FooEndpoint(asgi_scope, asgi_receive, asgi_send)

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    @pytest.mark.parametrize(
        ["encoding", "send_method", "data", "expected_result"],
        (
            pytest.param("bytes", "send_bytes", b"foo", {"bytes": b"foo", "type": "websocket.send"}, id="bytes"),
            pytest.param(
                "bytes", "send_text", "foo", {"code": 1003, "type": "websocket.close", "reason": ""}, id="bytes_wrong"
            ),
            pytest.param("text", "send_text", "foo", {"text": "foo", "type": "websocket.send"}, id="text"),
            pytest.param(
                "text", "send_bytes", b"foo", {"code": 1003, "type": "websocket.close", "reason": ""}, id="text_wrong"
            ),
            pytest.param(
                "json", "send_json", {"foo": "bar"}, {"text": '{"foo":"bar"}', "type": "websocket.send"}, id="json"
            ),
            pytest.param(
                "json",
                "send_bytes",
                b'{"foo": "bar"}',
                {"text": '{"foo":"bar"}', "type": "websocket.send"},
                id="json_using_bytes",
            ),
            pytest.param(
                "json",
                "send_text",
                b'{"foo":"bar"}',
                {"text": '{"foo":"bar"}', "type": "websocket.send"},
                id="json_using_text",
            ),
            pytest.param(
                "json", "send_bytes", b"foo", {"code": 1003, "type": "websocket.close", "reason": ""}, id="json_wrong"
            ),
            pytest.param(
                None,
                "send_bytes",
                b"foo",
                {"bytes": b"foo", "type": "websocket.send"},
                id="default_encoding",
            ),
            pytest.param(
                "unknown",
                "send_bytes",
                b"foo",
                {"code": 1003, "type": "websocket.close", "reason": ""},
                id="unknown_encoding",
            ),
        ),
    )
    def test_receive(self, app, client, encoding, send_method, data, expected_result):
        encoding_ = encoding

        @app.websocket_route("/")
        class FooWebSocketEndpoint(endpoints.WebSocketEndpoint):
            encoding = encoding_

            async def on_receive(self, websocket: websockets.WebSocket, data: types.Data):
                await getattr(websocket, f"send_{encoding_ or 'bytes'}")(data)

        with client.websocket_connect("/") as ws:
            getattr(ws, send_method)(data)
            result = ws.receive()

        assert result == expected_result

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    def test_injecting_component(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(endpoints.WebSocketEndpoint):
            encoding = types.Encoding("bytes")

            async def on_connect(self, websocket: websockets.WebSocket):
                await websocket.accept()

            async def on_receive(self, websocket: websockets.WebSocket, data: types.Data, puppy: Puppy):
                await websocket.send_json({"puppy": puppy.name})

            async def on_disconnect(self, websocket: websockets.WebSocket, websocket_code: types.Code):
                pass

        with client.websocket_connect("/") as ws:
            ws.send_bytes(b"")
            result = ws.receive_json()

        assert result == {"puppy": "Canna"}

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    def test_fail_connecting(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(endpoints.WebSocketEndpoint):
            async def on_connect(self, websocket: websockets.WebSocket):
                raise Exception("Error connecting socket")

        with pytest.raises(Exception, match="Error connecting socket"), client.websocket_connect("/") as ws:
            ws.send_bytes("foo")

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    def test_fail_receiving(self, app, client):
        @app.websocket_route("/")
        class FooWebSocketEndpoint(endpoints.WebSocketEndpoint):
            async def on_receive(self, websocket: websockets.WebSocket, data: types.Data):
                raise ValueError("Foo")

        with pytest.raises(ValueError, match="Foo"), client.websocket_connect("/") as ws:
            ws.send_bytes("foo")
            result = ws.receive()

            assert result == {"code": 1011, "type": "websocket.close", "reason": ""}

    def test_init(self, app, asgi_scope, asgi_receive, asgi_send):
        with patch("flama.websockets.WebSocket") as websocket_mock:
            route = app.add_websocket_route("/", endpoints.WebSocketEndpoint)
            asgi_scope = types.Scope(
                {
                    **asgi_scope,
                    "app": app,
                    "root_app": app,
                    "type": "websocket",
                    "path": "/",
                    "path_params": {},
                    "endpoint": endpoints.WebSocketEndpoint,
                    "route": route,
                }
            )
            endpoint = endpoints.WebSocketEndpoint(asgi_scope, asgi_receive, asgi_send)
            assert endpoint.state == {
                "scope": asgi_scope,
                "receive": asgi_receive,
                "send": asgi_send,
                "exc": None,
                "app": app,
                "route": route,
                "websocket": websocket_mock(),
                "websocket_code": None,
                "websocket_encoding": None,
                "websocket_message": None,
            }

    def test_allowed_handlers(self, endpoint):
        assert endpoint.allowed_handlers() == {
            "WEBSOCKET_CONNECT": endpoint.__class__.on_connect,
            "WEBSOCKET_RECEIVE": endpoint.__class__.on_receive,
            "WEBSOCKET_DISCONNECT": endpoint.__class__.on_disconnect,
        }

    @pytest.mark.parametrize(
        ["endpoint_receive", "websocket_receive", "exception", "result_code", "result_message"],
        (
            pytest.param(
                [None, None, None],
                [
                    {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                    {"type": "websocket.disconnect", "code": 1000},
                ],
                None,
                1000,
                {"type": "websocket.disconnect", "code": 1000},
                id="ok",
            ),
            pytest.param(
                [None, None, None],
                [
                    {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                    starlette.websockets.WebSocketDisconnect(1006, "Abnormal Closure"),
                ],
                exceptions.WebSocketException(1006, "Abnormal Closure"),
                1006,
                {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                id="disconnect",
            ),
            pytest.param(
                [None, exceptions.WebSocketException(1003, "Unsupported Data"), None],
                [{"type": "websocket.receive", "code": 1000, "bytes": "foo"}],
                exceptions.WebSocketException(1003, "Unsupported Data"),
                1003,
                {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                id="websocket_exception",
            ),
            pytest.param(
                [None, ValueError("Foo"), None],
                [{"type": "websocket.receive", "code": 1000, "bytes": "foo"}],
                ValueError("Foo"),
                1011,
                {"type": "websocket.receive", "code": 1000, "bytes": "foo"},
                id="exception",
            ),
        ),
        indirect=["exception"],
    )
    async def test_dispatch(
        self, app, endpoint, endpoint_receive, websocket_receive, exception, result_code, result_message
    ):
        app.injector.inject = AsyncMock(side_effect=[AsyncMock(side_effect=x) for x in endpoint_receive])
        endpoint.state["websocket"].receive = AsyncMock(side_effect=websocket_receive)
        type(endpoint.state["websocket"]).is_connected = PropertyMock(side_effect=[True, False])

        with exception:
            await endpoint.dispatch()

        assert endpoint.state["websocket_code"] == result_code
        assert endpoint.state["websocket_message"] == result_message

    async def test_on_connect(self, endpoint):
        websocket = MagicMock(websockets.WebSocket)

        await endpoint.on_connect(websocket)

        assert websocket.accept.call_args_list == [call()]

    async def test_on_receive(self, endpoint):
        websocket = MagicMock(websockets.WebSocket)

        await endpoint.on_receive(websocket, b"foo")

    async def test_on_disconnect(self, endpoint):
        websocket = MagicMock(websockets.WebSocket)

        await endpoint.on_disconnect(websocket, types.Code(1000))

        assert websocket.close.call_args_list == [call(types.Code(1000))]
