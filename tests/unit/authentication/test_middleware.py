import uuid

import pytest

from flama import Flama
from flama.authentication.components import AccessTokenComponent
from flama.authentication.middleware import AuthenticationMiddleware
from flama.middleware import Middleware

TOKENS = {
    "permission": b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJwZXJtaXNzaW9ucyI6IFsiZmxhbWEudGVzdC5hdXRoI"
    b"l19LCAiaWF0IjogMTY5ODQxMjkzMX0=.NLhM8r2g1I_oHG0zAAsRqDAuwPVvzI95Lnz2K7uupmo=",
    "role": b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJyb2xlcyI6IHsiZm9vIjogWyJmbGFtYS50ZXN0LmF1dGgiXX1"
    b"9LCAiaWF0IjogMTY5ODQxMjI5OH0=.WK2PwipkiLATHsKwIsiljS_31h0-T6U0hZzoI62Skiw=",
    "empty": b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjoge30sICJpYXQiOiAxNjk4NDEzMDg3fQ==.xPwYcCE0Tq6UxVbhW"
    b"RGqT8vRliJxHAqHs12X0oHE1Vg=",
}


class TestCaseAuthenticationMiddleware:
    @pytest.fixture(scope="function")
    def secret(self):
        return uuid.UUID(int=0)

    @pytest.fixture(scope="function")
    def app(self, secret):
        return Flama(
            schema=None,
            docs=None,
            components=[AccessTokenComponent(secret=secret.bytes)],
            middleware=[Middleware(AuthenticationMiddleware, ignored=[r"/ignored.*"])],
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/no-auth/")
        def no_auth():
            return {"foo": "no-auth"}

        @app.route("/auth/", tags={"permissions": ["flama.test.auth"]})
        def auth():
            return {"foo": "auth"}

        @app.route("/ignored/", tags={"permissions": ["flama.test.auth"]})
        def ignored():
            return {"foo": "ignored"}

    @pytest.fixture(scope="function")
    def headers(self, request):
        if request.param is None:
            return None

        try:
            return {"access_token": f"Bearer {TOKENS[request.param].decode()}"}
        except KeyError:
            raise ValueError(f"Invalid token {request.param}")

    @pytest.fixture(scope="function")
    def cookies(self, request):
        if request.param is None:
            return None

        try:
            return {"access_token": TOKENS[request.param].decode()}
        except KeyError:
            raise ValueError(f"Invalid token {request.param}")

    @pytest.mark.parametrize(
        ["path", "method", "headers", "cookies", "status_code", "result"],
        (
            pytest.param("/auth/", "get", "permission", None, 200, {"foo": "auth"}, id="auth_header_token_permission"),
            pytest.param("/auth/", "get", "role", None, 200, {"foo": "auth"}, id="auth_header_token_role"),
            pytest.param(
                "/auth/",
                "get",
                "empty",
                None,
                403,
                {"detail": "Insufficient permissions", "error": None, "status_code": 403},
                id="auth_header_token_empty",
            ),
            pytest.param("/auth/", "get", None, "permission", 200, {"foo": "auth"}, id="auth_cookie_token_permission"),
            pytest.param("/auth/", "get", None, "role", 200, {"foo": "auth"}, id="auth_cookie_token_role"),
            pytest.param(
                "/auth/",
                "get",
                None,
                "empty",
                403,
                {"detail": "Insufficient permissions", "error": None, "status_code": 403},
                id="auth_cookie_token_empty",
            ),
            pytest.param(
                "/auth/",
                "get",
                None,
                None,
                401,
                {"detail": "Unauthorized", "error": None, "status_code": 401},
                id="auth_no_token",
            ),
            pytest.param(
                "/no-auth/", "get", "permission", None, 200, {"foo": "no-auth"}, id="no_auth_header_token_permission"
            ),
            pytest.param("/no-auth/", "get", "role", None, 200, {"foo": "no-auth"}, id="no_auth_header_token_role"),
            pytest.param(
                "/no-auth/", "get", None, "permission", 200, {"foo": "no-auth"}, id="no_auth_cookie_token_permission"
            ),
            pytest.param("/no-auth/", "get", None, "role", 200, {"foo": "no-auth"}, id="no_auth_cookie_token_role"),
            pytest.param("/no-auth/", "get", None, None, 200, {"foo": "no-auth"}, id="no_auth_no_token"),
            pytest.param("/ignored/", "get", None, None, 200, {"foo": "ignored"}, id="no_auth_no_token"),
            pytest.param(
                "/not-found/",
                "get",
                None,
                None,
                404,
                {"detail": "Not Found", "error": "HTTPException", "status_code": 404},
                id="not_found",
            ),
            pytest.param(
                "/auth/",
                "post",
                None,
                None,
                405,
                {"detail": "Method Not Allowed", "error": "HTTPException", "status_code": 405},
                id="method_not_allowed",
            ),
        ),
        indirect=["headers", "cookies"],
    )
    async def test_request(self, client, path, method, headers, cookies, status_code, result):
        client.headers = headers
        client.cookies = cookies
        response = await client.request(method, path)

        assert response.status_code == status_code
        assert response.json() == result
