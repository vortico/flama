import datetime
import http
import importlib.metadata
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import Flama, authentication, types
from flama.telemetry import Authentication, Endpoint, Error, Request, Response, TelemetryData, TelemetryMiddleware
from flama.telemetry.middleware import HTTPWrapper, WebSocketWrapper, Wrapper

SECRET = uuid.UUID(int=0)

TOKEN = (
    "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V"
    "28rM_b1UU62XCp9dg_5kg="
)
DECODED_TOKEN = authentication.AccessToken.decode(TOKEN.encode(), SECRET.bytes)


class TestCaseTelemetryMiddleware:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(
            schema=None,
            docs=None,
            components=[
                authentication.AccessTokenComponent(secret=SECRET.bytes),
                authentication.RefreshTokenComponent(secret=SECRET.bytes),
            ],
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.post("/{x:int}/", name="foo", tags={"foo": "bar"})
        def root(x: int, y: int, body: types.Body):
            return {"x": x, "y": y, "body": body}

        @app.post("/error/", name="error")
        def error():
            raise ValueError("foo")

        @app.post("/ignored/", name="ignored")
        def ignored():
            return "ignored"

        @app.post("/explicit-off/", name="explicit-off", tags={"telemetry": False})
        def explicit_off():
            return "explicit_off"

    @pytest.mark.parametrize(
        [
            "path",
            "request_params",
            "request_body",
            "request_cookies",
            "status_code",
            "response",
            "exception",
            "before",
            "after",
            "data",
        ],
        [
            pytest.param(
                "/1/",
                {"y": 1},
                b"body",
                {"access_token": TOKEN},
                http.HTTPStatus.OK,
                {"x": 1, "y": 1, "body": "body"},
                None,
                None,
                None,
                None,
                id="ok_no_hooks",
            ),
            pytest.param(
                "/1/",
                {"y": 1},
                b"body",
                {"access_token": TOKEN},
                http.HTTPStatus.OK,
                {"x": 1, "y": 1, "body": "body"},
                None,
                MagicMock(),
                MagicMock(),
                TelemetryData(
                    type="http",
                    endpoint=Endpoint(path="/{x}/", name="foo", tags={"foo": "bar"}),
                    authentication=Authentication(access=DECODED_TOKEN, refresh=None),
                    request=Request(
                        headers={
                            "host": "localapp",
                            "accept": "*/*",
                            "accept-encoding": "gzip, deflate",
                            "connection": "keep-alive",
                            "user-agent": f"flama/{importlib.metadata.version('flama')}",
                            "cookie": "access_token=eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiY"
                            "mFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V28rM_b1UU62XCp9dg_5kg=",
                            "content-length": "4",
                        },
                        cookies={
                            "access_token": {
                                "expires": "",
                                "path": "",
                                "comment": "",
                                "domain": "",
                                "max-age": "",
                                "secure": "",
                                "httponly": "",
                                "version": "",
                                "samesite": "",
                                "partitioned": "",
                                "value": "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJ"
                                "pYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V28rM_b1UU62XCp9dg_5kg=",
                            }
                        },
                        query_parameters={"y": "1"},
                        path_parameters={"x": 1},
                        body=b"body",
                    ),
                    response=Response(
                        headers={"content-length": "27", "content-type": "application/json"},
                        body=b'{"x":1,"y":1,"body":"body"}',
                        status_code=http.HTTPStatus.OK,
                    ),
                ),
                id="ok_sync_hooks",
            ),
            pytest.param(
                "/1/",
                {"y": 1},
                b"body",
                {"access_token": TOKEN},
                http.HTTPStatus.OK,
                {"x": 1, "y": 1, "body": "body"},
                None,
                AsyncMock(),
                AsyncMock(),
                TelemetryData(
                    type="http",
                    endpoint=Endpoint(path="/{x}/", name="foo", tags={"foo": "bar"}),
                    authentication=Authentication(access=DECODED_TOKEN, refresh=None),
                    request=Request(
                        headers={
                            "host": "localapp",
                            "accept": "*/*",
                            "accept-encoding": "gzip, deflate",
                            "connection": "keep-alive",
                            "user-agent": f"flama/{importlib.metadata.version('flama')}",
                            "cookie": "access_token=eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiY"
                            "mFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V28rM_b1UU62XCp9dg_5kg=",
                            "content-length": "4",
                        },
                        cookies={
                            "access_token": {
                                "expires": "",
                                "path": "",
                                "comment": "",
                                "domain": "",
                                "max-age": "",
                                "secure": "",
                                "httponly": "",
                                "version": "",
                                "samesite": "",
                                "partitioned": "",
                                "value": "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJ"
                                "pYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V28rM_b1UU62XCp9dg_5kg=",
                            }
                        },
                        query_parameters={"y": "1"},
                        path_parameters={"x": 1},
                        body=b"body",
                    ),
                    response=Response(
                        headers={"content-length": "27", "content-type": "application/json"},
                        body=b'{"x":1,"y":1,"body":"body"}',
                        status_code=http.HTTPStatus.OK,
                    ),
                ),
                id="ok_async_hooks",
            ),
            pytest.param(
                "/error/",
                {},
                None,
                {},
                http.HTTPStatus.OK,
                None,
                ValueError("foo"),
                None,
                None,
                None,
                id="error_no_hooks",
            ),
            pytest.param(
                "/error/",
                {},
                None,
                {},
                http.HTTPStatus.OK,
                None,
                ValueError("foo"),
                MagicMock(),
                MagicMock(),
                TelemetryData(
                    type="http",
                    endpoint=Endpoint(path="/error/", name="error", tags={}),
                    authentication=Authentication(access=None, refresh=None),
                    request=Request(
                        headers={
                            "host": "localapp",
                            "accept": "*/*",
                            "accept-encoding": "gzip, deflate",
                            "connection": "keep-alive",
                            "user-agent": f"flama/{importlib.metadata.version('flama')}",
                            "content-length": "0",
                        },
                        cookies={},
                        query_parameters={},
                        path_parameters={},
                        body=b"",
                    ),
                    error=Error(detail="foo", status_code=None),
                ),
                id="error_sync_hooks",
            ),
            pytest.param(
                "/error/",
                {},
                None,
                {},
                http.HTTPStatus.OK,
                None,
                ValueError("foo"),
                AsyncMock(),
                AsyncMock(),
                TelemetryData(
                    type="http",
                    endpoint=Endpoint(path="/error/", name="error", tags={}),
                    authentication=Authentication(access=None, refresh=None),
                    request=Request(
                        headers={
                            "host": "localapp",
                            "accept": "*/*",
                            "accept-encoding": "gzip, deflate",
                            "connection": "keep-alive",
                            "user-agent": f"flama/{importlib.metadata.version('flama')}",
                            "content-length": "0",
                        },
                        cookies={},
                        query_parameters={},
                        path_parameters={},
                        body=b"",
                    ),
                    error=Error(detail="foo", status_code=None),
                ),
                id="error_async_hooks",
            ),
            pytest.param(
                "/ignored/",
                {},
                None,
                {},
                http.HTTPStatus.OK,
                "ignored",
                None,
                AsyncMock(),
                AsyncMock(),
                None,
                id="ignored",
            ),
            pytest.param(
                "/explicit-off/",
                {},
                None,
                {},
                http.HTTPStatus.OK,
                "explicit_off",
                None,
                AsyncMock(),
                AsyncMock(),
                None,
                id="explicit_off",
            ),
            pytest.param(
                "/not-found/",
                {},
                None,
                {},
                http.HTTPStatus.NOT_FOUND,
                {"status_code": 404, "detail": "Not Found", "error": "HTTPException"},
                None,
                None,
                None,
                None,
                id="not_found",
            ),
        ],
        indirect=["exception"],
    )
    async def test_request(
        self,
        app,
        client,
        path,
        request_params,
        request_body,
        request_cookies,
        status_code,
        response,
        exception,
        before,
        after,
        data,
    ):
        app.add_middleware(TelemetryMiddleware(before=before, after=after, ignored=[r"/ignored.*"]))

        client.cookies = request_cookies

        now = datetime.datetime.now()

        if data:
            data.request.timestamp = now
            if data.response:
                data.response.timestamp = now
            if data.error:
                data.error.timestamp = now

            if sys.version_info < (3, 14):  # PORT: Replace compat when stop supporting 3.13
                for cookie in [name for name, cookie in data.request.cookies.items() if "partitioned" in cookie]:
                    del data.request.cookies[cookie]["partitioned"]

        with exception, patch("datetime.datetime", MagicMock(now=MagicMock(return_value=now))):
            r = await client.post(path, params=request_params, content=request_body)

            assert r.status_code == status_code
            assert r.json() == response

        if before:
            assert before.call_args_list == ([call(data)] if data else [])

        if after:
            assert after.call_args_list == ([call(data)] if data else [])


@pytest.fixture
def telemetry_data():
    def _factory(scope_type: str = "websocket") -> TelemetryData:
        return TelemetryData(
            type=scope_type,
            endpoint=Endpoint(path="/", name=None, tags={}),
            authentication=Authentication(access=None, refresh=None),
            request=Request(headers={}, cookies={}, query_parameters={}, path_parameters={}, body=b""),
        )

    return _factory


class TestCaseHTTPWrapper:
    def test_build(self, telemetry_data):
        data = telemetry_data("http")
        wrapper = Wrapper.build("http", AsyncMock(), data)

        assert isinstance(wrapper, HTTPWrapper)

    @pytest.mark.parametrize(
        ["message", "expected_body"],
        [
            pytest.param(
                types.Message({"type": "http.request", "body": b"abc"}),
                b"abc",
                id="request_accumulates_body",
            ),
            pytest.param(
                types.Message({"type": "http.disconnect"}),
                b"",
                id="non_request_passthrough",
            ),
        ],
    )
    async def test_receive(self, telemetry_data, message, expected_body):
        data = telemetry_data("http")
        wrapper = HTTPWrapper(AsyncMock(), data)
        wrapper._receive = AsyncMock(return_value=message)

        msg = await wrapper.receive()

        assert msg["type"] == message["type"]
        assert data.request.body == expected_body

    @pytest.mark.parametrize(
        ["message", "expected_status", "expected_headers", "expected_body"],
        [
            pytest.param(
                types.Message({"type": "http.response.start", "status": 200, "headers": [(b"x-foo", b"bar")]}),
                200,
                {"x-foo": "bar"},
                b"",
                id="response_start",
            ),
            pytest.param(
                types.Message({"type": "http.response.body", "body": b"hello"}),
                None,
                None,
                b"hello",
                id="response_body",
            ),
            pytest.param(
                types.Message({"type": "http.response.trailers"}),
                None,
                None,
                b"",
                id="other_message",
            ),
        ],
    )
    async def test_send(self, telemetry_data, message, expected_status, expected_headers, expected_body):
        data = telemetry_data("http")
        wrapper = HTTPWrapper(AsyncMock(), data)
        wrapper._response_body = b""
        wrapper._send = AsyncMock()

        await wrapper.send(message)

        if expected_status is not None:
            assert wrapper._response_status_code == expected_status
        if expected_headers is not None:
            assert wrapper._response_headers == expected_headers
        assert wrapper._response_body == expected_body
        wrapper._send.assert_awaited_once_with(message)


class TestCaseWebSocketWrapper:
    def test_build(self, telemetry_data):
        data = telemetry_data()
        wrapper = Wrapper.build("websocket", AsyncMock(), data)

        assert isinstance(wrapper, WebSocketWrapper)

    @pytest.mark.parametrize(
        ["message", "expected_body", "expected_status"],
        [
            pytest.param(
                types.Message({"type": "websocket.receive", "body": b"abc"}),
                b"abc",
                None,
                id="receive_accumulates_body",
            ),
            pytest.param(
                types.Message({"type": "websocket.disconnect", "code": 1000, "reason": "gone"}),
                b"gone",
                1000,
                id="disconnect",
            ),
            pytest.param(
                types.Message({"type": "websocket.disconnect", "reason": "x"}),
                b"x",
                None,
                id="disconnect_default_code",
            ),
            pytest.param(
                types.Message({"type": "websocket.connect"}),
                b"",
                None,
                id="other_message",
            ),
        ],
    )
    async def test_receive(self, telemetry_data, message, expected_body, expected_status):
        data = telemetry_data()
        wrapper = WebSocketWrapper(AsyncMock(), data)
        wrapper._response_body = b""
        wrapper._receive = AsyncMock(return_value=message)

        msg = await wrapper.receive()

        assert msg["type"] == message["type"]
        assert wrapper._response_body == expected_body
        if expected_status is not None:
            assert wrapper._response_status_code == expected_status

    @pytest.mark.parametrize(
        ["message", "expected_request_body", "expected_response_body", "expected_status"],
        [
            pytest.param(
                types.Message({"type": "websocket.send", "bytes": b"bin"}),
                b"bin",
                b"",
                None,
                id="send_bytes",
            ),
            pytest.param(
                types.Message({"type": "websocket.send", "text": "txt"}),
                b"txt",
                b"",
                None,
                id="send_text",
            ),
            pytest.param(
                types.Message({"type": "websocket.close", "code": 4000, "reason": "bye"}),
                b"",
                b"bye",
                4000,
                id="close",
            ),
            pytest.param(
                types.Message({"type": "websocket.close", "code": 1000}),
                b"",
                b"",
                1000,
                id="close_default_reason",
            ),
            pytest.param(
                types.Message({"type": "websocket.ping"}),
                b"",
                b"",
                None,
                id="other_message",
            ),
        ],
    )
    async def test_send(
        self,
        telemetry_data,
        message,
        expected_request_body,
        expected_response_body,
        expected_status,
    ):
        data = telemetry_data()
        wrapper = WebSocketWrapper(AsyncMock(), data)
        wrapper._response_body = b""
        wrapper._send = AsyncMock()

        await wrapper.send(message)

        assert data.request.body == expected_request_body
        assert wrapper._response_body == expected_response_body
        if expected_status is not None:
            assert wrapper._response_status_code == expected_status
        wrapper._send.assert_awaited_once_with(message)
