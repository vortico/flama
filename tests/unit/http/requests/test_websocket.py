from unittest.mock import AsyncMock, call

import pytest

from flama import exceptions, types
from flama.http.data_structures import WebSocketStatus
from flama.http.requests.websocket import WebSocket, WebSocketClose


class TestCaseWebSocket:
    @pytest.fixture
    def scope(self, asgi_scope):
        asgi_scope["type"] = "websocket"
        return asgi_scope

    @pytest.fixture
    def receive(self):
        return AsyncMock()

    @pytest.fixture
    def send(self):
        return AsyncMock()

    @pytest.fixture
    def websocket(self, scope, receive, send):
        return WebSocket(scope, receive, send)

    def test_init(self, websocket):
        assert websocket.client_status == WebSocketStatus.CONNECTING
        assert websocket.application_status == WebSocketStatus.CONNECTING

    @pytest.mark.parametrize(
        ["client_status", "receive_message", "data", "expected_result", "expected_client_status", "exception"],
        [
            pytest.param(
                WebSocketStatus.CONNECTING,
                types.Message({"type": "websocket.connect"}),
                None,
                types.Message({"type": "websocket.connect"}),
                WebSocketStatus.CONNECTED,
                None,
                id="connect",
            ),
            pytest.param(
                WebSocketStatus.CONNECTING,
                types.Message({"type": "websocket.send"}),
                None,
                None,
                WebSocketStatus.CONNECTING,
                RuntimeError("websocket.connect"),
                id="connect_wrong_type",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.receive", "text": "hello", "bytes": b"hello"}),
                None,
                types.Message({"type": "websocket.receive", "text": "hello", "bytes": b"hello"}),
                WebSocketStatus.CONNECTED,
                None,
                id="message",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.receive", "bytes": b"\x00\x01"}),
                "bytes",
                b"\x00\x01",
                WebSocketStatus.CONNECTED,
                None,
                id="bytes",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.receive", "text": "hello"}),
                "text",
                "hello",
                WebSocketStatus.CONNECTED,
                None,
                id="text",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.receive", "bytes": b'{"k": "v"}'}),
                "json",
                {"k": "v"},
                WebSocketStatus.CONNECTED,
                None,
                id="json_from_bytes",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.receive", "text": '{"k": "v"}'}),
                "json",
                {"k": "v"},
                WebSocketStatus.CONNECTED,
                None,
                id="json_from_text",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.disconnect", "code": 1001}),
                None,
                None,
                WebSocketStatus.DISCONNECTED,
                exceptions.WebSocketDisconnect(1001),
                id="disconnect",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.connect"}),
                None,
                None,
                WebSocketStatus.CONNECTED,
                (RuntimeError, "websocket.receive"),
                id="connected_wrong_type",
            ),
            pytest.param(
                WebSocketStatus.DISCONNECTED,
                None,
                None,
                None,
                WebSocketStatus.DISCONNECTED,
                (RuntimeError, "disconnect message"),
                id="already_disconnected",
            ),
        ],
        indirect=["exception"],
    )
    async def test_receive(
        self,
        websocket,
        receive,
        client_status,
        receive_message,
        data,
        expected_result,
        expected_client_status,
        exception,
    ):
        websocket.client_status = client_status
        if receive_message is not None:
            receive.return_value = receive_message

        with exception:
            result = await websocket.receive(data=data)
            assert result == expected_result

        assert websocket.client_status == expected_client_status

    @pytest.mark.parametrize(
        [
            "application_status",
            "send_kwargs",
            "send_side_effect",
            "expected_status",
            "expected_sent",
            "exception",
        ],
        [
            # -- message construction --
            pytest.param(
                WebSocketStatus.CONNECTED,
                {},
                None,
                WebSocketStatus.CONNECTED,
                None,
                ValueError("must be provided"),
                id="no_args",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"message": types.Message({"type": "websocket.send"}), "data": b"x"},
                None,
                WebSocketStatus.CONNECTED,
                None,
                ValueError("mutually exclusive"),
                id="message_and_data",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"message": types.Message({"type": "websocket.send"}), "json": {"x": 1}},
                None,
                WebSocketStatus.CONNECTED,
                None,
                ValueError("mutually exclusive"),
                id="message_and_json",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"data": b"\xff"},
                None,
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.send", "bytes": b"\xff"}),
                None,
                id="data_bytes",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"data": "hello"},
                None,
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.send", "text": "hello"}),
                None,
                id="data_text",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"json": {"a": 1}},
                None,
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.send", "bytes": b'{"a": 1}'}),
                None,
                id="data_json",
            ),
            # -- CONNECTING state --
            pytest.param(
                WebSocketStatus.CONNECTING,
                {"message": types.Message({"type": "websocket.accept"})},
                None,
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.accept"}),
                None,
                id="connecting_accept",
            ),
            pytest.param(
                WebSocketStatus.CONNECTING,
                {"message": types.Message({"type": "websocket.close", "code": 1000})},
                None,
                WebSocketStatus.DISCONNECTED,
                types.Message({"type": "websocket.close", "code": 1000}),
                None,
                id="connecting_close",
            ),
            pytest.param(
                WebSocketStatus.CONNECTING,
                {"message": types.Message({"type": "websocket.http.response.start", "status": 403})},
                None,
                WebSocketStatus.RESPONSE,
                types.Message({"type": "websocket.http.response.start", "status": 403}),
                None,
                id="connecting_response_start",
            ),
            pytest.param(
                WebSocketStatus.CONNECTING,
                {"message": types.Message({"type": "websocket.send"})},
                None,
                WebSocketStatus.CONNECTING,
                None,
                RuntimeError("websocket.accept"),
                id="connecting_wrong_type",
            ),
            # -- CONNECTED state --
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"message": types.Message({"type": "websocket.send", "text": "hi"})},
                None,
                WebSocketStatus.CONNECTED,
                types.Message({"type": "websocket.send", "text": "hi"}),
                None,
                id="connected_send",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"message": types.Message({"type": "websocket.close", "code": 1000})},
                None,
                WebSocketStatus.DISCONNECTED,
                types.Message({"type": "websocket.close", "code": 1000}),
                None,
                id="connected_close",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"message": types.Message({"type": "websocket.accept"})},
                None,
                WebSocketStatus.CONNECTED,
                None,
                RuntimeError("websocket.send"),
                id="connected_wrong_type",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                {"message": types.Message({"type": "websocket.send", "text": "hi"})},
                OSError("Broken pipe"),
                WebSocketStatus.DISCONNECTED,
                None,
                exceptions.WebSocketDisconnect(1006),
                id="connected_oserror",
            ),
            # -- RESPONSE state --
            pytest.param(
                WebSocketStatus.RESPONSE,
                {
                    "message": types.Message(
                        {"type": "websocket.http.response.body", "body": b"data", "more_body": True}
                    )
                },
                None,
                WebSocketStatus.RESPONSE,
                types.Message({"type": "websocket.http.response.body", "body": b"data", "more_body": True}),
                None,
                id="response_body_more",
            ),
            pytest.param(
                WebSocketStatus.RESPONSE,
                {
                    "message": types.Message(
                        {"type": "websocket.http.response.body", "body": b"done", "more_body": False}
                    )
                },
                None,
                WebSocketStatus.DISCONNECTED,
                types.Message({"type": "websocket.http.response.body", "body": b"done", "more_body": False}),
                None,
                id="response_body_final",
            ),
            pytest.param(
                WebSocketStatus.RESPONSE,
                {"message": types.Message({"type": "websocket.send"})},
                None,
                WebSocketStatus.RESPONSE,
                None,
                RuntimeError("websocket.http.response.body"),
                id="response_wrong_type",
            ),
            # -- DISCONNECTED state --
            pytest.param(
                WebSocketStatus.DISCONNECTED,
                {"message": types.Message({"type": "websocket.send"})},
                None,
                WebSocketStatus.DISCONNECTED,
                None,
                RuntimeError("close message"),
                id="disconnected",
            ),
        ],
        indirect=["exception"],
    )
    async def test_send(
        self,
        websocket,
        send,
        application_status,
        send_kwargs,
        send_side_effect,
        expected_status,
        expected_sent,
        exception,
    ):
        websocket.application_status = application_status
        if send_side_effect is not None:
            send.side_effect = send_side_effect

        with exception:
            await websocket.send(**send_kwargs)
            if expected_sent is not None:
                assert send.call_args[0][0] == expected_sent

        assert websocket.application_status == expected_status

    @pytest.mark.parametrize(
        ["client_status", "receive_message", "subprotocol", "headers", "receive_called"],
        [
            pytest.param(
                WebSocketStatus.CONNECTING,
                types.Message({"type": "websocket.connect"}),
                None,
                None,
                True,
                id="connecting",
            ),
            pytest.param(
                WebSocketStatus.CONNECTING,
                types.Message({"type": "websocket.connect"}),
                "graphql-ws",
                None,
                True,
                id="subprotocol",
            ),
            pytest.param(
                WebSocketStatus.CONNECTING,
                types.Message({"type": "websocket.connect"}),
                None,
                [(b"x-key", b"val")],
                True,
                id="headers",
            ),
            pytest.param(
                WebSocketStatus.CONNECTED,
                None,
                None,
                None,
                False,
                id="already_connected",
            ),
        ],
    )
    async def test_accept(
        self, websocket, receive, send, client_status, receive_message, subprotocol, headers, receive_called
    ):
        websocket.client_status = client_status
        if receive_message is not None:
            receive.return_value = receive_message

        await websocket.accept(subprotocol=subprotocol, headers=headers)

        if receive_called:
            receive.assert_awaited_once()
        else:
            receive.assert_not_awaited()

        msg = send.call_args[0][0]
        assert msg["type"] == "websocket.accept"
        assert msg["subprotocol"] == subprotocol
        assert msg["headers"] == list(headers or [])
        assert websocket.application_status == WebSocketStatus.CONNECTED

    @pytest.mark.parametrize(
        ["code", "reason", "expected_reason"],
        [
            pytest.param(1001, "going away", "going away", id="custom"),
            pytest.param(1000, None, "", id="defaults"),
        ],
    )
    async def test_close(self, websocket, send, code, reason, expected_reason):
        await websocket.close(code, reason)

        msg = send.call_args[0][0]
        assert msg == types.Message({"type": "websocket.close", "code": code, "reason": expected_reason})
        assert websocket.application_status == WebSocketStatus.DISCONNECTED

    @pytest.mark.parametrize(
        ["extensions", "exception"],
        [
            pytest.param({"websocket.http.response": {}}, None, id="supported"),
            pytest.param({}, (RuntimeError, "Denial Response"), id="unsupported"),
        ],
        indirect=["exception"],
    )
    async def test_send_denial_response(self, websocket, scope, extensions, exception):
        scope["extensions"] = extensions
        response = AsyncMock()

        with exception:
            await websocket.send_denial_response(response)
            response.assert_awaited_once_with(scope, websocket._receive, websocket._send)

    @pytest.mark.parametrize(
        ["status", "expected"],
        [
            pytest.param(WebSocketStatus.CONNECTING, True, id="connecting"),
            pytest.param(WebSocketStatus.CONNECTED, False, id="connected"),
            pytest.param(WebSocketStatus.DISCONNECTED, False, id="disconnected"),
        ],
    )
    def test_is_connecting(self, websocket, status, expected):
        websocket.client_status = status

        assert websocket.is_connecting is expected

    @pytest.mark.parametrize(
        ["status", "expected"],
        [
            pytest.param(WebSocketStatus.CONNECTING, False, id="connecting"),
            pytest.param(WebSocketStatus.CONNECTED, True, id="connected"),
            pytest.param(WebSocketStatus.DISCONNECTED, False, id="disconnected"),
        ],
    )
    def test_is_connected(self, websocket, status, expected):
        websocket.client_status = status

        assert websocket.is_connected is expected

    @pytest.mark.parametrize(
        ["status", "expected"],
        [
            pytest.param(WebSocketStatus.CONNECTING, False, id="connecting"),
            pytest.param(WebSocketStatus.CONNECTED, False, id="connected"),
            pytest.param(WebSocketStatus.DISCONNECTED, True, id="disconnected"),
        ],
    )
    def test_is_disconnected(self, websocket, status, expected):
        websocket.client_status = status

        assert websocket.is_disconnected is expected


class TestCaseWebSocketClose:
    @pytest.mark.parametrize(
        ["code", "reason", "expected_code", "expected_reason"],
        [
            pytest.param(1001, "going away", 1001, "going away", id="custom"),
            pytest.param(1000, None, 1000, "", id="defaults"),
        ],
    )
    def test_init(self, code, reason, expected_code, expected_reason):
        close = WebSocketClose(code=code, reason=reason)

        assert close.code == expected_code
        assert close.reason == expected_reason

    @pytest.mark.parametrize(
        ["code", "reason"],
        [
            pytest.param(1001, "going away", id="custom"),
            pytest.param(1000, "", id="defaults"),
        ],
    )
    async def test_call(self, asgi_scope, asgi_receive, asgi_send, code, reason):
        close = WebSocketClose(code=code, reason=reason)

        await close(asgi_scope, asgi_receive, asgi_send)

        assert asgi_send.call_args_list == [
            call(types.Message({"type": "websocket.close", "code": code, "reason": reason}))
        ]
