import pytest
from _pytest.mark import param
from starlette.testclient import TestClient

from flama.applications.flama import Flama
from flama.endpoints import WebSocketEndpoint
from flama.types import http, websockets


class TestCaseDataValidation:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None)

    @pytest.fixture(scope="function")
    def client(self, app):
        return TestClient(app)

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
                {"files": {"a": ("b", "123")}, "data": {"b": "42"}},
                200,
                {"data": {"a": {"filename": "b", "content": "123"}, "b": "42"}},
                id="multipart",
            ),
            # Misc
            param({"data": b"...", "headers": {"content-type": "unknown"}}, 415, None, id="unknown body type"),
            param(
                {"data": b"...", "headers": {"content-type": "application/json"}}, 400, None, id="json parse failure"
            ),
        ],
    )
    def test_request_data(self, request_params, response_status, response_json, app, client):
        @app.route("/request_data/", methods=["POST"])
        async def get_request_data(data: http.RequestData):
            try:
                data = {
                    key: value
                    if not hasattr(value, "filename")
                    else {"filename": value.filename, "content": (await value.read()).decode("utf-8")}
                    for key, value in data.items()
                }
            except Exception:
                pass

            return {"data": data}

        response = client.post("/request_data/", **request_params)
        assert response.status_code == response_status, str(response.content)
        if response_json is not None:
            assert response.json() == response_json

    @pytest.mark.parametrize(
        "encoding,send_method,data,expected_result",
        [
            # bytes
            param("bytes", "bytes", b"foo", {"type": "websocket.send", "bytes": b"foo"}, id="bytes"),
            param("bytes", "text", b"foo", {"type": "websocket.close", "code": 1003}, id="bytes wrong format"),
            # text
            param("text", "text", "foo", {"type": "websocket.send", "text": "foo"}, id="text"),
            param("text", "bytes", "foo", {"type": "websocket.close", "code": 1003}, id="text wrong format"),
            # json
            param(
                "json",
                "json",
                {"foo": "bar"},
                {"type": "websocket.send", "text": '{"foo": "bar"}'},
                id="json from json",
            ),
            param(
                "json",
                "text",
                '{"foo": "bar"}',
                {"type": "websocket.send", "text": '{"foo": "bar"}'},
                id="json from text",
            ),
            param(
                "json",
                "bytes",
                b'{"foo": "bar"}',
                {"type": "websocket.send", "text": '{"foo": "bar"}'},
                id="json from bytes",
            ),
            param("json", "bytes", b'{"foo":', {"type": "websocket.close", "code": 1003}, id="json wrong format"),
        ],
    )
    def test_websocket_message_data(self, encoding, send_method, data, expected_result, app, client):
        encoding_ = encoding

        @app.websocket_route("/websocket/")
        class Endpoint(WebSocketEndpoint):
            encoding = encoding_

            async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data):
                await getattr(websocket, f"send_{encoding}")(data)

        with client.websocket_connect("/websocket/") as ws:
            getattr(ws, f"send_{send_method}")(data)
            message = ws.receive()

        assert message == expected_result
