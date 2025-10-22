import http

import pytest

from flama import endpoints, types, websockets


class TestCaseRequestDataValidation:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/request_data/", methods=["POST"])
        async def get_request_data(data: types.RequestData):
            return {
                "data": {
                    key: value
                    if not hasattr(value, "filename")
                    else {"filename": value.filename, "content": (await value.read()).decode("utf-8")}
                    for key, value in data.data.items()
                }
                if data.data
                else None
            }

    @pytest.mark.parametrize(
        ["params", "response"],
        [
            # JSON
            pytest.param(
                {"json": {"abc": 123}},
                (
                    http.HTTPStatus.OK,
                    {"data": {"abc": 123}},
                ),
                id="valid json body",
            ),
            pytest.param(
                {},
                (
                    http.HTTPStatus.OK,
                    {"data": None},
                ),
                id="empty json body",
            ),
            # Urlencoding
            pytest.param(
                {"data": {"abc": 123}},
                (
                    http.HTTPStatus.OK,
                    {"data": {"abc": "123"}},
                ),
                id="valid urlencoded body",
            ),
            pytest.param(
                {"headers": {"content-type": "application/x-www-form-urlencoded"}},
                (
                    http.HTTPStatus.OK,
                    {"data": None},
                ),
                id="empty urlencoded body",
            ),
            # Multipart
            pytest.param(
                {"files": {"a": ("b", b"123")}, "data": {"b": "42"}},
                (
                    http.HTTPStatus.OK,
                    {"data": {"a": {"filename": "b", "content": "123"}, "b": "42"}},
                ),
                id="multipart",
            ),
            # Misc
            pytest.param(
                {"content": b"...", "headers": {"content-type": "unknown"}},
                (
                    http.HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    None,
                ),
                id="unknown body type",
            ),
            pytest.param(
                {"content": b"...", "headers": {"content-type": "application/json"}},
                (
                    http.HTTPStatus.BAD_REQUEST,
                    None,
                ),
                id="json parse failure",
            ),
        ],
    )
    async def test_request_data(self, app, client, params, response):
        status_code, response = response
        r = await client.request("post", "/request_data/", **params)
        assert r.status_code == status_code, str(r.content)
        if response is not None:
            assert r.json() == response


@pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
class TestCaseWebsocketDataValidation:
    @pytest.mark.parametrize(
        ["encoding", "send_method", "data", "expected_result"],
        [
            # bytes
            pytest.param("bytes", "bytes", b"foo", {"type": "websocket.send", "bytes": b"foo"}, id="bytes"),
            pytest.param(
                "bytes",
                "text",
                b"foo",
                {"type": "websocket.close", "code": 1003, "reason": ""},
                id="bytes wrong format",
            ),
            # text
            pytest.param("text", "text", "foo", {"type": "websocket.send", "text": "foo"}, id="text"),
            pytest.param(
                "text", "bytes", "foo", {"type": "websocket.close", "code": 1003, "reason": ""}, id="text wrong format"
            ),
            # json
            pytest.param(
                "json",
                "json",
                {"foo": "bar"},
                {"type": "websocket.send", "text": '{"foo":"bar"}'},
                id="json from json",
            ),
            pytest.param(
                "json",
                "text",
                '{"foo": "bar"}',
                {"type": "websocket.send", "text": '{"foo":"bar"}'},
                id="json from text",
            ),
            pytest.param(
                "json",
                "bytes",
                b'{"foo": "bar"}',
                {"type": "websocket.send", "text": '{"foo":"bar"}'},
                id="json from bytes",
            ),
            pytest.param(
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
