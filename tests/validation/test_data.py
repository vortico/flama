import pytest
from _pytest.mark import param

from flama import endpoints, types, websockets


class TestCaseDataValidation:
    @pytest.mark.parametrize(
        "request_params,response_status,response_json",
        [
            # JSON
            param({"json": {"abc": 123}}, 200, {"data": {"abc": 123}}, id="valid json body"),
            param({}, 200, {"data": None}, id="empty json body"),
            # Urlencoding
            param({"data": {"abc": 123}}, 200, {"data": {"abc": "123"}}, id="valid urlencoded body"),
            param(
                {"headers": {"content-type": "application/x-www-form-urlencoded"}},
                200,
                {"data": None},
                id="empty urlencoded body",
            ),
            # Multipart
            param(
                {"files": {"a": ("b", b"123")}, "data": {"b": "42"}},
                200,
                {"data": {"a": {"filename": "b", "content": "123"}, "b": "42"}},
                id="multipart",
            ),
            # Misc
            param({"content": b"...", "headers": {"content-type": "unknown"}}, 415, None, id="unknown body type"),
            param(
                {"content": b"...", "headers": {"content-type": "application/json"}}, 400, None, id="json parse failure"
            ),
        ],
    )
    async def test_request_data(self, request_params, response_status, response_json, app, client):
        @app.route("/request_data/", methods=["POST"])
        async def get_request_data(data: types.RequestData):
            try:
                data = types.RequestData(
                    {
                        key: value
                        if not hasattr(value, "filename")
                        else {"filename": value.filename, "content": (await value.read()).decode("utf-8")}
                        for key, value in data.items()
                    }
                )
            except Exception:
                pass

            return {"data": data}

        response = await client.request("post", "/request_data/", **request_params)
        assert response.status_code == response_status, str(response.content)
        if response_json is not None:
            assert response.json() == response_json

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    @pytest.mark.parametrize(
        "encoding,send_method,data,expected_result",
        [
            # bytes
            param("bytes", "bytes", b"foo", {"type": "websocket.send", "bytes": b"foo"}, id="bytes"),
            param(
                "bytes",
                "text",
                b"foo",
                {"type": "websocket.close", "code": 1003, "reason": ""},
                id="bytes wrong format",
            ),
            # text
            param("text", "text", "foo", {"type": "websocket.send", "text": "foo"}, id="text"),
            param(
                "text", "bytes", "foo", {"type": "websocket.close", "code": 1003, "reason": ""}, id="text wrong format"
            ),
            # json
            param(
                "json",
                "json",
                {"foo": "bar"},
                {"type": "websocket.send", "text": '{"foo":"bar"}'},
                id="json from json",
            ),
            param(
                "json",
                "text",
                '{"foo": "bar"}',
                {"type": "websocket.send", "text": '{"foo":"bar"}'},
                id="json from text",
            ),
            param(
                "json",
                "bytes",
                b'{"foo": "bar"}',
                {"type": "websocket.send", "text": '{"foo":"bar"}'},
                id="json from bytes",
            ),
            param(
                "json",
                "bytes",
                b'{"foo":',
                {"type": "websocket.close", "code": 1003, "reason": ""},
                id="json wrong format",
            ),
        ],
    )
    def test_websocket_message_data(self, encoding, send_method, data, expected_result, app, client):
        encoding_ = encoding

        @app.websocket_route("/websocket/")
        class Endpoint(endpoints.WebSocketEndpoint):
            encoding = encoding_

            async def on_receive(self, websocket: websockets.WebSocket, data: types.Data):
                await getattr(websocket, f"send_{encoding}")(data)

        with client.websocket_connect("/websocket/") as ws:
            getattr(ws, f"send_{send_method}")(data)
            message = ws.receive()

        assert message == expected_result
