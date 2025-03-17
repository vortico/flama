import datetime
import http
import importlib.metadata
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import Flama, authentication, types
from flama.middleware import Middleware
from flama.telemetry import Authentication, Endpoint, Error, Request, Response, TelemetryData, TelemetryMiddleware

SECRET = uuid.UUID(int=0)

TOKEN = (
    "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V"
    "28rM_b1UU62XCp9dg_5kg="
)
DECODED_TOKEN = authentication.JWT.decode(TOKEN.encode(), SECRET.bytes)


class TestCaseTelemetryMiddleware:
    # TODO: WebSocketWrapper is not tested

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
                    authentication=Authentication(access=authentication.AccessToken(DECODED_TOKEN), refresh=None),
                    request=Request(
                        headers={
                            "host": "localapp",
                            "accept": "*/*",
                            "accept-encoding": "gzip, deflate",
                            "connection": "keep-alive",
                            "user-agent": f"flama/{importlib.metadata.version('flama')}",
                            "content-length": "4",
                            "cookie": "access_token=eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiY"
                            "mFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V28rM_b1UU62XCp9dg_5kg=",
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
                    authentication=Authentication(access=authentication.AccessToken(DECODED_TOKEN), refresh=None),
                    request=Request(
                        headers={
                            "host": "localapp",
                            "accept": "*/*",
                            "accept-encoding": "gzip, deflate",
                            "connection": "keep-alive",
                            "user-agent": f"flama/{importlib.metadata.version('flama')}",
                            "content-length": "4",
                            "cookie": "access_token=eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiY"
                            "mFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V28rM_b1UU62XCp9dg_5kg=",
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
        app.add_middleware(Middleware(TelemetryMiddleware, before=before, after=after, ignored=[r"/ignored.*"]))

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
