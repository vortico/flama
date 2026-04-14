import hashlib
import time

import pytest

from flama import Flama
from flama.client import Client
from flama.crypto.jws import JWS
from flama.http import Request
from flama.middleware.sessions import SessionMiddleware

SECRET_KEY = b"test-secret-key"


class TestCaseSessionMiddleware:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, middleware=[SessionMiddleware(secret_key=SECRET_KEY)])

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/set-session/")
        def set_session(request: Request):
            request.session["user"] = "alice"
            return {"session": "set"}

        @app.route("/read-session/")
        def read_session(request: Request):
            return {"user": request.session.get("user", "anonymous")}

        @app.route("/clear-session/")
        def clear_session(request: Request):
            request.session.clear()
            return {"session": "cleared"}

    @pytest.fixture(scope="function")
    def signing_key(self):
        return hashlib.sha256(SECRET_KEY).digest()

    @pytest.fixture(scope="function")
    def session_cookie(self, request, signing_key):
        if request.param is None:
            return None

        if request.param == "valid":
            payload = {"data": {"user": "bob"}, "iat": 2_000_000_000}
            return JWS.encode(header={"alg": "HS256"}, payload=payload, key=signing_key).decode()

        if request.param == "tampered":
            return "tampered-data"

        return None

    @pytest.mark.parametrize(
        ["path", "method", "session_cookie", "status_code", "body", "has_set_cookie"],
        [
            pytest.param("/set-session/", "get", None, 200, {"session": "set"}, True, id="set_session"),
            pytest.param("/read-session/", "get", "valid", 200, {"user": "bob"}, True, id="read_valid_session"),
            pytest.param(
                "/read-session/", "get", "tampered", 200, {"user": "anonymous"}, False, id="read_tampered_session"
            ),
            pytest.param("/read-session/", "get", None, 200, {"user": "anonymous"}, False, id="read_no_session"),
            pytest.param("/clear-session/", "get", "valid", 200, {"session": "cleared"}, True, id="clear_session"),
        ],
        indirect=["session_cookie"],
    )
    async def test_request(self, client, path, method, session_cookie, status_code, body, has_set_cookie):
        if session_cookie:
            client.cookies = {"session": session_cookie}

        response = await client.request(method, path)

        assert response.status_code == status_code
        assert response.json() == body

        if has_set_cookie:
            assert "set-cookie" in response.headers

    async def test_https_only_and_domain_cookie_flags(self):
        app = Flama(
            schema=None,
            docs=None,
            middleware=[SessionMiddleware(secret_key=SECRET_KEY, https_only=True, domain="example.com", max_age=120)],
        )

        @app.route("/set-session/")
        def set_session(request: Request):
            request.session["user"] = "alice"
            return {"session": "set"}

        async with Client(app=app) as c:
            response = await c.request("get", "/set-session/")

        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert "secure" in cookie
        assert "domain=example.com" in cookie

    async def test_expired_session_treated_as_empty(self):
        app = Flama(
            schema=None,
            docs=None,
            middleware=[SessionMiddleware(secret_key=SECRET_KEY, max_age=120)],
        )

        @app.route("/read-session/")
        def read_session(request: Request):
            return {"user": request.session.get("user", "anonymous")}

        signing_key = hashlib.sha256(SECRET_KEY).digest()
        payload = {"data": {"user": "carol"}, "iat": int(time.time()) - 10_000}
        token = JWS.encode(header={"alg": "HS256"}, payload=payload, key=signing_key).decode()

        async with Client(app=app) as c:
            c.cookies = {"session": token}
            response = await c.request("get", "/read-session/")

        assert response.status_code == 200
        assert response.json() == {"user": "anonymous"}

    async def test_no_max_age(self):
        app = Flama(
            schema=None,
            docs=None,
            middleware=[SessionMiddleware(secret_key=SECRET_KEY, max_age=None)],
        )

        @app.route("/read-session/")
        def read_session(request: Request):
            return {"user": request.session.get("user", "anonymous")}

        signing_key = hashlib.sha256(SECRET_KEY).digest()
        payload = {"data": {"user": "infinite"}, "iat": 0}
        token = JWS.encode(header={"alg": "HS256"}, payload=payload, key=signing_key).decode()

        async with Client(app=app) as c:
            c.cookies = {"session": token}
            response = await c.request("get", "/read-session/")

        assert response.status_code == 200
        assert response.json() == {"user": "infinite"}
