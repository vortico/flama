import uuid

import pytest

from flama import Flama
from flama.authentication.components import JWTComponent
from flama.authentication.jwt.jwt import JWT

TOKEN = (
    b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V"
    b"28rM_b1UU62XCp9dg_5kg="
)


class TestCaseJWTComponent:
    @pytest.fixture(scope="function")
    def secret(self):
        return uuid.UUID(int=0)

    @pytest.fixture(scope="function")
    def app(self, secret):
        return Flama(
            schema=None,
            docs=None,
            components=[
                JWTComponent(
                    secret=secret.bytes,
                    header_key="Authorization",
                    header_prefix="Bearer",
                    cookie_key="flama_authentication",
                )
            ],
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.get("/")
        def jwt(token: JWT):
            return token.asdict()

    @pytest.mark.parametrize(
        ["params", "status_code", "result"],
        (
            pytest.param(
                {"headers": {"Authorization": f"Bearer {TOKEN.decode()}"}},
                200,
                {"header": {"alg": "HS256", "typ": "JWT"}, "payload": {"data": {"foo": "bar"}, "iat": 0}},
                id="headers",
            ),
            pytest.param(
                {"headers": {"Authorization": "token"}},
                400,
                {
                    "detail": {
                        "description": "Authentication header must be 'Authorization: Bearer <token>'",
                        "error": "JWTException",
                    },
                    "error": "HTTPException",
                    "status_code": 400,
                },
                id="header_wrong_format",
            ),
            pytest.param(
                {"headers": {"Authorization": "Foo token"}},
                400,
                {
                    "detail": {
                        "description": "Authentication header must be 'Authorization: Bearer <token>'",
                        "error": "JWTException",
                    },
                    "error": "HTTPException",
                    "status_code": 400,
                },
                id="header_wrong_prefix",
            ),
            pytest.param(
                {"cookies": {"flama_authentication": TOKEN.decode()}},
                200,
                {"header": {"alg": "HS256", "typ": "JWT"}, "payload": {"data": {"foo": "bar"}, "iat": 0}},
                id="cookies",
            ),
            pytest.param(
                {},
                401,
                {"detail": "Unauthorized", "error": "HTTPException", "status_code": 401},
                id="unauthorized",
            ),
            pytest.param(
                {
                    "cookies": {
                        "flama_authentication": "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyI"
                        "n0sICJpYXQiOiAwfQ==.0000",
                    }
                },
                401,
                {
                    "detail": {
                        "description": "Signature verification failed for token 'eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVC"
                        "J9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.0000'",
                        "error": "JWTValidateException",
                    },
                    "error": "HTTPException",
                    "status_code": 401,
                },
                id="invalid_token",
            ),
        ),
    )
    async def test_injection(self, client, status_code, result, params):
        response = await client.request("get", "/", **params)

        assert response.status_code == status_code
        assert response.json() == result
