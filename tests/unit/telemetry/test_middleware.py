import datetime
import http
import importlib.metadata
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import Flama, authentication, types
from flama.telemetry import Authentication, Endpoint, Error, Request, Response, TelemetryData, TelemetryMiddleware
from flama.telemetry.data_structures import _Body
from flama.telemetry.middleware import HTTPWrapper, WebSocketWrapper, Wrapper

SECRET = uuid.UUID(int=0)

MAX_BODY = 1024

TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImZvbyI6ImJhciJ9LCJpYXQiOjB9.PWRDHe1X53ydEpCCKW8_oDMVveSlvdqg"
    "xLhFjLk7BNk="
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
                            "cookie": f"access_token={TOKEN}",
                            "content-length": "4",
                        },
                        cookies={"access_token": {"value": TOKEN}},
                        query_parameters={"y": "1"},
                        path_parameters={"x": 1},
                        body=_Body(content=b"body"),
                    ),
                    response=Response(
                        headers={"content-length": "27", "content-type": "application/json"},
                        body=_Body(content=b'{"x":1,"y":1,"body":"body"}'),
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
                            "cookie": f"access_token={TOKEN}",
                            "content-length": "4",
                        },
                        cookies={"access_token": {"value": TOKEN}},
                        query_parameters={"y": "1"},
                        path_parameters={"x": 1},
                        body=_Body(content=b"body"),
                    ),
                    response=Response(
                        headers={"content-length": "27", "content-type": "application/json"},
                        body=_Body(content=b'{"x":1,"y":1,"body":"body"}'),
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
                        body=_Body(content=b""),
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
                        body=_Body(content=b""),
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

        with exception, patch("datetime.datetime", MagicMock(now=MagicMock(return_value=now))):
            r = await client.post(path, params=request_params, content=request_body)

            assert r.status_code == status_code
            assert r.json() == response

        if before:
            assert before.call_args_list == ([call(data)] if data else [])

        if after:
            assert after.call_args_list == ([call(data)] if data else [])


@pytest.fixture(scope="function")
def telemetry_data():
    def _factory(scope_type: str = "websocket") -> TelemetryData:
        return TelemetryData(
            type=scope_type,
            endpoint=Endpoint(path="/", name=None, tags={}),
            authentication=Authentication(access=None, refresh=None),
            request=Request(headers={}, cookies={}, query_parameters={}, path_parameters={}, body=_Body(content=b"")),
        )

    return _factory


class TestCaseHTTPWrapper:
    def test_build(self, telemetry_data):
        data = telemetry_data("http")
        wrapper = Wrapper.build("http", AsyncMock(), data, max_body=MAX_BODY)

        assert isinstance(wrapper, HTTPWrapper)

    @pytest.mark.parametrize(
        ["max_body", "message", "expected_body", "expected_truncated"],
        [
            pytest.param(
                MAX_BODY,
                types.Message({"type": "http.request", "body": b"abc"}),
                b"abc",
                False,
                id="request_accumulates_body",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "http.disconnect"}),
                b"",
                False,
                id="non_request_passthrough",
            ),
            pytest.param(
                2,
                types.Message({"type": "http.request", "body": b"abc"}),
                b"ab",
                True,
                id="request_bounded",
            ),
            pytest.param(
                0,
                types.Message({"type": "http.request", "body": b"abc"}),
                b"",
                True,
                id="request_declined",
            ),
            pytest.param(
                None,
                types.Message({"type": "http.request", "body": b"abc"}),
                b"abc",
                False,
                id="request_unbounded",
            ),
        ],
    )
    async def test_receive(self, telemetry_data, max_body, message, expected_body, expected_truncated):
        data = telemetry_data("http")
        wrapper = HTTPWrapper(AsyncMock(), data, max_body=max_body)
        wrapper._receive = AsyncMock(return_value=message)

        msg = await wrapper.receive()

        assert msg["type"] == message["type"]
        assert data.request.body.content == expected_body
        assert data.request.body.truncated is expected_truncated

    @pytest.mark.parametrize(
        ["max_body", "message", "expected_status", "expected_headers", "expected_body", "expected_truncated"],
        [
            pytest.param(
                MAX_BODY,
                types.Message({"type": "http.response.start", "status": 200, "headers": [(b"x-foo", b"bar")]}),
                200,
                {"x-foo": "bar"},
                b"",
                False,
                id="response_start",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "http.response.body", "body": b"hello"}),
                None,
                None,
                b"hello",
                False,
                id="response_body",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "http.response.trailers"}),
                None,
                None,
                b"",
                False,
                id="other_message",
            ),
            pytest.param(
                2,
                types.Message({"type": "http.response.body", "body": b"hello"}),
                None,
                None,
                b"he",
                True,
                id="response_bounded",
            ),
            pytest.param(
                0,
                types.Message({"type": "http.response.body", "body": b"hello"}),
                None,
                None,
                b"",
                True,
                id="response_declined",
            ),
            pytest.param(
                None,
                types.Message({"type": "http.response.body", "body": b"hello"}),
                None,
                None,
                b"hello",
                False,
                id="response_unbounded",
            ),
        ],
    )
    async def test_send(
        self, telemetry_data, max_body, message, expected_status, expected_headers, expected_body, expected_truncated
    ):
        data = telemetry_data("http")
        wrapper = HTTPWrapper(AsyncMock(), data, max_body=max_body)
        wrapper._send = AsyncMock()

        await wrapper.send(message)

        if expected_status is not None:
            assert wrapper._response.status_code == expected_status
        if expected_headers is not None:
            assert wrapper._response.headers == expected_headers
        assert wrapper._response.body.content == expected_body
        assert wrapper._response.body.truncated is expected_truncated
        assert wrapper._send.await_args_list == [call(message)]


class TestCaseWebSocketWrapper:
    def test_build(self, telemetry_data):
        data = telemetry_data()
        wrapper = Wrapper.build("websocket", AsyncMock(), data, max_body=MAX_BODY)

        assert isinstance(wrapper, WebSocketWrapper)

    @pytest.mark.parametrize(
        ["max_body", "message", "expected_body", "expected_truncated", "expected_reason", "expected_status"],
        [
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.receive", "bytes": b"bin"}),
                b"bin",
                False,
                b"",
                None,
                id="receive_bytes",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.receive", "text": "txt"}),
                b"txt",
                False,
                b"",
                None,
                id="receive_text",
            ),
            pytest.param(
                2,
                types.Message({"type": "websocket.receive", "bytes": b"bin"}),
                b"bi",
                True,
                b"",
                None,
                id="receive_bounded",
            ),
            pytest.param(
                0,
                types.Message({"type": "websocket.receive", "bytes": b"bin"}),
                b"",
                True,
                b"",
                None,
                id="receive_declined",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.disconnect", "code": 1000, "reason": "gone"}),
                b"",
                False,
                b"gone",
                1000,
                id="disconnect",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.disconnect", "reason": "x"}),
                b"",
                False,
                b"x",
                None,
                id="disconnect_default_code",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.connect"}),
                b"",
                False,
                b"",
                None,
                id="other_message",
            ),
        ],
    )
    async def test_receive(
        self, telemetry_data, max_body, message, expected_body, expected_truncated, expected_reason, expected_status
    ):
        data = telemetry_data()
        wrapper = WebSocketWrapper(AsyncMock(), data, max_body=max_body)
        wrapper._receive = AsyncMock(return_value=message)

        msg = await wrapper.receive()

        assert msg["type"] == message["type"]
        assert data.request.body.content == expected_body
        assert data.request.body.truncated is expected_truncated
        assert wrapper._response.body.content == expected_reason
        if expected_status is not None:
            assert wrapper._response.status_code == expected_status

    @pytest.mark.parametrize(
        ["max_body", "message", "expected_body", "expected_truncated", "expected_status"],
        [
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.send", "bytes": b"bin"}),
                b"bin",
                False,
                None,
                id="send_bytes",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.send", "text": "txt"}),
                b"txt",
                False,
                None,
                id="send_text",
            ),
            pytest.param(
                2,
                types.Message({"type": "websocket.send", "bytes": b"bin"}),
                b"bi",
                True,
                None,
                id="send_bounded",
            ),
            pytest.param(
                0,
                types.Message({"type": "websocket.send", "bytes": b"bin"}),
                b"",
                True,
                None,
                id="send_declined",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.close", "code": 4000, "reason": "bye"}),
                b"bye",
                False,
                4000,
                id="close",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.close", "code": 1000}),
                b"",
                False,
                1000,
                id="close_default_reason",
            ),
            pytest.param(
                MAX_BODY,
                types.Message({"type": "websocket.ping"}),
                b"",
                False,
                None,
                id="other_message",
            ),
        ],
    )
    async def test_send(self, telemetry_data, max_body, message, expected_body, expected_truncated, expected_status):
        data = telemetry_data()
        wrapper = WebSocketWrapper(AsyncMock(), data, max_body=max_body)
        wrapper._send = AsyncMock()

        await wrapper.send(message)

        assert data.request.body.content == b""
        assert wrapper._response.body.content == expected_body
        assert wrapper._response.body.truncated is expected_truncated
        if expected_status is not None:
            assert wrapper._response.status_code == expected_status
        assert wrapper._send.await_args_list == [call(message)]
