from unittest.mock import AsyncMock, call, patch

import pytest
import starlette.websockets

from flama import websockets


class TestCaseWebSocket:
    @pytest.fixture
    def websocket(self, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "websocket"
        return websockets.WebSocket(asgi_scope, asgi_receive, asgi_send)

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    @pytest.mark.parametrize(
        ["encoding", "send_method", "data", "expected_result", "exception"],
        (
            pytest.param("bytes", "send_bytes", b"foo", {"bytes": b"foo", "type": "websocket.send"}, None, id="bytes"),
            pytest.param(
                "bytes",
                "send_text",
                "foo",
                {"code": 1003, "type": "websocket.close", "reason": ""},
                ValueError("Foo"),
                id="bytes_wrong",
            ),
            pytest.param("text", "send_text", "foo", {"text": "foo", "type": "websocket.send"}, None, id="text"),
            pytest.param(
                "text",
                "send_bytes",
                b"foo",
                {"code": 1003, "type": "websocket.close", "reason": ""},
                ValueError("Foo"),
                id="text_wrong",
            ),
            pytest.param(
                "json",
                "send_json",
                {"foo": "bar"},
                {"text": '{"foo":"bar"}', "type": "websocket.send"},
                None,
                id="json",
            ),
            pytest.param(
                "json",
                "send_bytes",
                b"foo",
                {"code": 1003, "type": "websocket.close", "reason": ""},
                ValueError("Foo"),
                id="json_wrong",
            ),
        ),
        indirect=["exception"],
    )
    def test_receive(self, app, client, encoding, send_method, data, expected_result, exception):
        @app.websocket_route("/")
        async def foo_websocket(websocket: websockets.WebSocket):
            try:
                await websocket.accept()
                if exception.exception:
                    raise exception.exception
                await getattr(websocket, f"send_{encoding or 'bytes'}")(data)
            except Exception as e:
                await websocket.close(1003)
                raise e from None
            else:
                await websocket.close()

        with exception, client.websocket_connect("/") as ws:
            getattr(ws, send_method)(data)
            result = ws.receive()

        assert result == expected_result

    def test_is_connecting(self, websocket):
        websocket.client_state = starlette.websockets.WebSocketState.CONNECTING

        assert websocket.is_connecting

    def test_is_connected(self, websocket):
        websocket.client_state = starlette.websockets.WebSocketState.CONNECTED

        assert websocket.is_connected

    def test_is_disconnected(self, websocket):
        websocket.client_state = starlette.websockets.WebSocketState.DISCONNECTED

        assert websocket.is_disconnected


class TestCaseClose:
    @pytest.fixture
    def close(self):
        return websockets.Close()

    async def test_call(self, close, asgi_scope, asgi_receive, asgi_send):
        with patch.object(starlette.websockets.WebSocketClose, "__call__", new=AsyncMock()) as super_call_mock:
            await close(asgi_scope, asgi_receive, asgi_send)

            assert super_call_mock.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]
