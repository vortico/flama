import datetime
import http
import uuid
from unittest.mock import MagicMock, patch

import pytest

from flama import Flama, authentication
from flama.exceptions import HTTPException
from flama.telemetry.data_structures import Authentication, Endpoint, Error, Request, Response, TelemetryData

TOKEN = (
    "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V"
    "28rM_b1UU62XCp9dg_5kg="
)


@pytest.fixture(scope="function")
def secret():
    return uuid.UUID(int=0)


@pytest.fixture(scope="function")
def app(secret):
    return Flama(
        schema=None,
        docs=None,
        components=[
            authentication.AccessTokenComponent(secret=secret.bytes),
            authentication.RefreshTokenComponent(secret=secret.bytes),
        ],
    )


@pytest.fixture(scope="function", autouse=True)
def add_routes(app):
    @app.route("/")
    def root(): ...

    @app.route("/query_parameters/")
    def query_parameters(x: int):
        return {"x": x}

    @app.route("/path_parameters/{x:int}/")
    def path_parameters(x: int):
        return {"x": x}

    @app.route("/tags/", tags={"foo": "bar"})
    def tags(): ...

    @app.route("/name/", name="foo")
    def name(): ...


@pytest.fixture(scope="function")
def asgi_scope(app, asgi_scope):
    asgi_scope["app"] = app
    return asgi_scope


class TestCaseAuthentication:
    @pytest.mark.parametrize(
        ["scope", "result"],
        [
            pytest.param(
                {"path": "/"},
                {"access": None, "refresh": None},
                id="no_auth",
            ),
            pytest.param(
                {"path": "/", "headers": [(b"cookie", f"access_token={TOKEN}".encode())]},
                {
                    "access": {
                        "header": {"alg": "HS256", "typ": "JWT"},
                        "payload": {"data": {"foo": "bar"}, "iat": 0},
                    },
                    "refresh": None,
                },
                id="access",
            ),
            pytest.param(
                {"path": "/", "headers": [(b"cookie", f"refresh_token={TOKEN}".encode())]},
                {
                    "access": None,
                    "refresh": {
                        "header": {"alg": "HS256", "typ": "JWT"},
                        "payload": {"data": {"foo": "bar"}, "iat": 0},
                    },
                },
                id="refresh",
            ),
            pytest.param(
                {
                    "path": "/",
                    "headers": [(b"cookie", f"access_token={TOKEN}; refresh_token={TOKEN}".encode())],
                },
                {
                    "access": {
                        "header": {"alg": "HS256", "typ": "JWT"},
                        "payload": {"data": {"foo": "bar"}, "iat": 0},
                    },
                    "refresh": {
                        "header": {"alg": "HS256", "typ": "JWT"},
                        "payload": {"data": {"foo": "bar"}, "iat": 0},
                    },
                },
                id="access_and_refresh",
            ),
        ],
    )
    async def test_from_scope(self, asgi_scope, asgi_receive, asgi_send, scope, result):
        asgi_scope.update(scope)
        now = datetime.datetime.now()
        with patch("datetime.datetime", MagicMock(now=MagicMock(return_value=now))):
            data = await Authentication.from_scope(scope=asgi_scope, receive=asgi_receive, send=asgi_send)

            assert data.to_dict() == result


class TestCaseEndpoint:
    @pytest.mark.parametrize(
        ["scope", "result"],
        [
            pytest.param(
                {"path": "/"},
                {"name": "root", "path": "/", "tags": {}},
                id="default_name",
            ),
            pytest.param(
                {"path": "/name/"},
                {"name": "foo", "path": "/name/", "tags": {}},
                id="explicit_name",
            ),
            pytest.param(
                {"path": "/tags/"},
                {"name": "tags", "path": "/tags/", "tags": {"foo": "bar"}},
                id="tags",
            ),
        ],
    )
    async def test_from_scope(self, asgi_scope, asgi_receive, asgi_send, scope, result):
        asgi_scope.update(scope)
        now = datetime.datetime.now()
        with patch("datetime.datetime", MagicMock(now=MagicMock(return_value=now))):
            data = await Endpoint.from_scope(scope=asgi_scope, receive=asgi_receive, send=asgi_send)

            assert data.to_dict() == result


class TestCaseRequest:
    @pytest.mark.parametrize(
        ["scope", "result"],
        [
            pytest.param(
                {"path": "/"},
                {
                    "body": b"",
                    "cookies": {},
                    "headers": {},
                    "path_parameters": {},
                    "query_parameters": {},
                },
                id="empty",
            ),
            pytest.param(
                {"path": "/path_parameters/1/"},
                {
                    "body": b"",
                    "cookies": {},
                    "headers": {},
                    "path_parameters": {"x": 1},
                    "query_parameters": {},
                },
                id="path_parameters",
            ),
            pytest.param(
                {"path": "/query_parameters/", "query_string": b"x=1"},
                {
                    "body": b"",
                    "cookies": {},
                    "headers": {},
                    "path_parameters": {},
                    "query_parameters": {"x": "1"},
                },
                id="query_parameters",
            ),
            pytest.param(
                {"path": "/", "headers": [(b"foo", b"bar")]},
                {
                    "body": b"",
                    "cookies": {},
                    "headers": {"foo": "bar"},
                    "path_parameters": {},
                    "query_parameters": {},
                },
                id="headers",
            ),
            pytest.param(
                {"path": "/", "headers": [(b"cookie", b"foo=bar")]},
                {
                    "body": b"",
                    "cookies": {
                        "foo": {
                            "comment": "",
                            "domain": "",
                            "expires": "",
                            "httponly": "",
                            "max-age": "",
                            "path": "",
                            "samesite": "",
                            "secure": "",
                            "value": "bar",
                            "version": "",
                        }
                    },
                    "headers": {"cookie": "foo=bar"},
                    "path_parameters": {},
                    "query_parameters": {},
                },
                id="cookies",
            ),
        ],
    )
    async def test_from_scope(self, asgi_scope, asgi_receive, asgi_send, scope, result):
        asgi_scope.update(scope)
        now = datetime.datetime.now()
        result["timestamp"] = now.isoformat()
        with patch("datetime.datetime", MagicMock(now=MagicMock(return_value=now))):
            data = await Request.from_scope(scope=asgi_scope, receive=asgi_receive, send=asgi_send)

            assert data.to_dict() == result


class TestCaseResponse:
    @pytest.mark.parametrize(
        ["headers", "body", "status_code", "result"],
        [
            pytest.param(
                {},
                b"",
                None,
                {
                    "body": b"",
                    "cookies": {},
                    "headers": {},
                    "status_code": None,
                },
                id="empty",
            ),
            pytest.param(
                {},
                b"foo",
                http.HTTPStatus.OK,
                {
                    "body": b"foo",
                    "cookies": {},
                    "headers": {},
                    "status_code": http.HTTPStatus.OK,
                },
                id="body",
            ),
            pytest.param(
                {"foo": "bar"},
                b"",
                http.HTTPStatus.OK,
                {
                    "body": b"",
                    "cookies": {},
                    "headers": {"foo": "bar"},
                    "status_code": http.HTTPStatus.OK,
                },
                id="headers",
            ),
            pytest.param(
                {"cookie": "foo=bar"},
                b"",
                http.HTTPStatus.OK,
                {
                    "body": b"",
                    "cookies": {
                        "foo": {
                            "comment": "",
                            "domain": "",
                            "expires": "",
                            "httponly": "",
                            "max-age": "",
                            "path": "",
                            "samesite": "",
                            "secure": "",
                            "value": "bar",
                            "version": "",
                        }
                    },
                    "headers": {"cookie": "foo=bar"},
                    "status_code": http.HTTPStatus.OK,
                },
                id="cookies",
            ),
        ],
    )
    def test_init(self, headers, body, status_code, result):
        now = datetime.datetime.now()
        result["timestamp"] = now.isoformat()
        with patch("datetime.datetime", MagicMock(now=MagicMock(return_value=now))):
            data = Response(headers=headers, body=body, status_code=status_code)

            assert data.to_dict() == result


class TestCaseError:
    @pytest.mark.parametrize(
        ["exception", "result"],
        [
            pytest.param(
                ValueError("foo"),
                {"detail": "foo", "status_code": None},
                id="exception",
            ),
            pytest.param(
                HTTPException(status_code=400, detail="foo"),
                {"detail": "foo", "status_code": 400},
                id="http",
            ),
        ],
    )
    async def test_from_exception(self, exception, result):
        now = datetime.datetime.now()
        result["timestamp"] = now.isoformat()
        with patch("datetime.datetime", MagicMock(now=MagicMock(return_value=now))):
            try:
                raise exception
            except Exception as e:
                error = await Error.from_exception(exception=e)

            assert error.to_dict() == result


class TestCaseTelemetryData:
    async def test_from_scope(self, asgi_scope, asgi_receive, asgi_send):
        now = datetime.datetime.now()
        with patch("datetime.datetime", MagicMock(now=MagicMock(return_value=now))):
            data = await TelemetryData.from_scope(scope=asgi_scope, receive=asgi_receive, send=asgi_send)

            assert data.to_dict() == {
                "authentication": {"access": None, "refresh": None},
                "endpoint": {"name": "root", "path": "/", "tags": {}},
                "error": None,
                "extra": {},
                "request": {
                    "body": b"",
                    "cookies": {},
                    "headers": {},
                    "path_parameters": {},
                    "query_parameters": {},
                    "timestamp": now.isoformat(),
                },
                "response": None,
                "type": "http",
            }
