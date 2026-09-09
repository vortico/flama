import typing as t
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


class TestCaseKeyResolution:
    TOKENS: t.ClassVar[dict[str, bytes]] = {
        "one": b"eyJhbGciOiJIUzI1NiIsImtpZCI6Im9uZSIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImZvbyI6ImJhciJ9LCJpYXQiOjB9."
        b"Z0UzER9wuehlx4xjeWjDUYJeUeHsbrHGklxBS3q4cDM=",
        "two": b"eyJhbGciOiJIUzI1NiIsImtpZCI6InR3byIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImZvbyI6ImJhciJ9LCJpYXQiOjB9."
        b"fKGKhoKhoFITep5l4UKbDJ7CJ4oCa1jK4SChKOEIa0I=",
    }

    @pytest.fixture(scope="function", params=["sync", "async"])
    def app(self, request):
        keys = {"one": uuid.UUID(int=1).bytes, "two": uuid.UUID(int=2).bytes}

        def resolver(kid):
            try:
                return keys[kid]
            except KeyError:
                raise authentication.exceptions.Unauthorized()

        async def async_resolver(kid):
            return resolver(kid)

        return Flama(
            schema=None,
            docs=None,
            components=[
                authentication.AccessTokenComponent(resolver=resolver if request.param == "sync" else async_resolver)
            ],
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.get("/")
        def access_token(token: authentication.AccessToken):
            return token.to_dict()

    @pytest.mark.parametrize(
        ["token", "status_code", "kid"],
        (
            pytest.param("one", 200, "one", id="first_key"),
            pytest.param("two", 200, "two", id="second_key"),
        ),
    )
    async def test_injection(self, client, token, status_code, kid):
        client.headers = {"access_token": f"Bearer {self.TOKENS[token].decode()}"}

        response = await client.request("get", "/")

        assert response.status_code == status_code
        assert response.json()["header"]["kid"] == kid

    @pytest.mark.parametrize(
        ["token", "status_code"],
        (
            pytest.param(TOKEN, 401, id="key_not_named"),
            pytest.param(
                b"eyJhbGciOiJIUzI1NiIsImtpZCI6InRocmVlIiwidHlwIjoiSldUIn0.eyJkYXRhIjp7ImZvbyI6ImJhciJ9LCJpYXQiOjB9."
                b"0000",
                401,
                id="key_not_known",
            ),
            pytest.param(b"NQ==.format.0000", 401, id="header_is_not_an_object"),
        ),
    )
    async def test_injection_refused(self, client, token, status_code):
        client.headers = {"access_token": f"Bearer {token.decode()}"}

        response = await client.request("get", "/")

        assert response.status_code == status_code


class TestCaseTokenComponentConfiguration:
    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        (
            pytest.param({"secret": b"secret"}, None, id="secret"),
            pytest.param({"resolver": lambda kid: b"secret"}, None, id="resolver"),
            pytest.param(
                {},
                ValueError("Give either a secret or a resolver, not both and not neither"),
                id="neither",
            ),
            pytest.param(
                {"secret": b"secret", "resolver": lambda kid: b"secret"},
                ValueError("Give either a secret or a resolver, not both and not neither"),
                id="both",
            ),
        ),
        indirect=["exception"],
    )
    @pytest.mark.parametrize(
        "component",
        (
            pytest.param(authentication.AccessTokenComponent, id="access"),
            pytest.param(authentication.RefreshTokenComponent, id="refresh"),
        ),
    )
    def test_init(self, component, kwargs, exception):
        with exception:
            assert component(**kwargs) is not None


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
