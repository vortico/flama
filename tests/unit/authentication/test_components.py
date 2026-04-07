import uuid

import pytest

from flama import Flama, authentication

TOKEN = (
    b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V"
    b"28rM_b1UU62XCp9dg_5kg="
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


class TestCaseAccessTokenComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.get("/")
        def access_token(token: authentication.AccessToken):
            return token.to_dict()

    @pytest.mark.parametrize(
        ["headers", "cookies", "status_code", "result"],
        (
            pytest.param(
                {"access_token": f"Bearer {TOKEN.decode()}"},
                None,
                200,
                {"header": {"alg": "HS256", "typ": "JWT"}, "payload": {"data": {"foo": "bar"}, "iat": 0}},
                id="headers",
            ),
            pytest.param(
                {"access_token": "token"},
                None,
                400,
                {
                    "detail": {
                        "description": "Authentication header must be 'access_token: Bearer <token>'",
                        "error": "JWTException",
                    },
                    "error": "HTTPException",
                    "status_code": 400,
                },
                id="header_wrong_format",
            ),
            pytest.param(
                {"access_token": "Foo token"},
                None,
                400,
                {
                    "detail": {
                        "description": "Authentication header must be 'access_token: Bearer <token>'",
                        "error": "JWTException",
                    },
                    "error": "HTTPException",
                    "status_code": 400,
                },
                id="header_wrong_prefix",
            ),
            pytest.param(
                None,
                {"access_token": TOKEN.decode()},
                200,
                {"header": {"alg": "HS256", "typ": "JWT"}, "payload": {"data": {"foo": "bar"}, "iat": 0}},
                id="cookies",
            ),
            pytest.param(
                None,
                None,
                401,
                {"detail": "Unauthorized", "error": "HTTPException", "status_code": 401},
                id="unauthorized",
            ),
            pytest.param(
                None,
                {
                    "access_token": "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyI"
                    "n0sICJpYXQiOiAwfQ==.0000",
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
    async def test_injection(self, client, status_code, result, headers, cookies):
        client.headers = headers
        client.cookies = cookies
        response = await client.request("get", "/")

        assert response.status_code == status_code
        assert response.json() == result


class TestCaseRefreshTokenComponent:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.get("/")
        def refresh_token(token: authentication.RefreshToken):
            return token.to_dict()

    @pytest.mark.parametrize(
        ["headers", "cookies", "status_code", "result"],
        (
            pytest.param(
                {"refresh_token": f"Bearer {TOKEN.decode()}"},
                None,
                200,
                {"header": {"alg": "HS256", "typ": "JWT"}, "payload": {"data": {"foo": "bar"}, "iat": 0}},
                id="headers",
            ),
            pytest.param(
                {"refresh_token": "token"},
                None,
                400,
                {
                    "detail": {
                        "description": "Authentication header must be 'refresh_token: Bearer <token>'",
                        "error": "JWTException",
                    },
                    "error": "HTTPException",
                    "status_code": 400,
                },
                id="header_wrong_format",
            ),
            pytest.param(
                {"refresh_token": "Foo token"},
                None,
                400,
                {
                    "detail": {
                        "description": "Authentication header must be 'refresh_token: Bearer <token>'",
                        "error": "JWTException",
                    },
                    "error": "HTTPException",
                    "status_code": 400,
                },
                id="header_wrong_prefix",
            ),
            pytest.param(
                None,
                {"refresh_token": TOKEN.decode()},
                200,
                {"header": {"alg": "HS256", "typ": "JWT"}, "payload": {"data": {"foo": "bar"}, "iat": 0}},
                id="cookies",
            ),
            pytest.param(
                None,
                None,
                401,
                {"detail": "Unauthorized", "error": "HTTPException", "status_code": 401},
                id="unauthorized",
            ),
            pytest.param(
                None,
                {
                    "refresh_token": "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyI"
                    "n0sICJpYXQiOiAwfQ==.0000",
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
    async def test_injection(self, client, status_code, result, headers, cookies):
        client.headers = headers
        client.cookies = cookies
        response = await client.request("get", "/")

        assert response.status_code == status_code
        assert response.json() == result
