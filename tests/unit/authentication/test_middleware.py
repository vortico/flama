import uuid
from http import HTTPStatus

import pytest

from flama import Flama
from flama.authentication.components import AccessTokenComponent
from flama.authentication.exceptions import KeysUnavailable
from flama.authentication.jwt import JWT
from flama.authentication.middleware import AuthenticationMiddleware
from flama.client import Client

RESOURCE = "https://api.example.com/resource/"
METADATA = "https://api.example.com/.well-known/oauth-protected-resource/resource/"
CLAIMS = {
    "scope": {"scope": "flama.test.auth other"},
    "scope_list": {"scope": ["flama.test.auth"]},
    "role": {"roles": ["admin"]},
    "scope_and_role": {"scope": "flama.test.auth", "roles": ["admin"]},
    # Claims of tokens issued before scopes and roles followed the standards, which grant nothing now.
    "legacy_permissions": {"permissions": ["flama.test.auth"]},
    "legacy_roles": {"roles": {"admin": ["flama.test.auth"]}},
    "empty": {},
    "audience": {"scope": "flama.test.auth", "aud": RESOURCE},
    "audience_only": {"aud": [RESOURCE, "https://other.example.com"]},
    "other_audience": {"scope": "flama.test.auth", "aud": "https://other.example.com"},
}
# Names the key "outage".
OUTAGE_TOKEN = b"eyJhbGciOiJIUzI1NiIsImtpZCI6Im91dGFnZSIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImZvbyI6ImJhciJ9LCJpYXQiOjB9.0000"


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
            middleware=[AuthenticationMiddleware(ignored=[r"/ignored.*"])],
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/no-auth/")
        def no_auth():
            return {"foo": "no-auth"}

        @app.route("/scoped/", tags={"permissions": ["flama.test.auth"]})
        def scoped():
            return {"foo": "scoped"}

        @app.route("/roled/", tags={"roles": ["admin"]})
        def roled():
            return {"foo": "roled"}

        @app.route("/both/", tags={"permissions": ["flama.test.auth"], "roles": ["admin"]})
        def both():
            return {"foo": "both"}

        @app.route("/resource/", tags={"permissions": ["flama.test.auth"], "resource": RESOURCE})
        def resource():
            return {"foo": "resource"}

        @app.route("/resource-only/", tags={"resource": RESOURCE})
        def resource_only():
            return {"foo": "resource-only"}

        @app.route("/ignored/", tags={"permissions": ["flama.test.auth"]})
        def ignored():
            return {"foo": "ignored"}

    @pytest.mark.parametrize(
        ["path", "method", "claims", "cookie", "status_code", "result", "challenge"],
        (
            pytest.param("/scoped/", "get", "scope", False, 200, {"foo": "scoped"}, None, id="scope"),
            pytest.param("/scoped/", "get", "scope_list", False, 200, {"foo": "scoped"}, None, id="scope_as_list"),
            pytest.param("/scoped/", "get", "scope", True, 200, {"foo": "scoped"}, None, id="scope_in_cookie"),
            pytest.param(
                "/scoped/",
                "get",
                "empty",
                False,
                403,
                "Insufficient permissions",
                'Bearer error="insufficient_scope", scope="flama.test.auth"',
                id="scope_missing",
            ),
            pytest.param(
                "/scoped/",
                "get",
                "legacy_permissions",
                False,
                403,
                "Insufficient permissions",
                'Bearer error="insufficient_scope", scope="flama.test.auth"',
                id="legacy_permissions_grant_nothing",
            ),
            pytest.param(
                "/scoped/",
                "get",
                "legacy_roles",
                False,
                403,
                "Insufficient permissions",
                'Bearer error="insufficient_scope", scope="flama.test.auth"',
                id="legacy_roles_grant_nothing",
            ),
            pytest.param(
                "/scoped/",
                "get",
                None,
                False,
                401,
                "Unauthorized",
                'Bearer scope="flama.test.auth"',
                id="scope_without_token",
            ),
            pytest.param("/roled/", "get", "role", False, 200, {"foo": "roled"}, None, id="role"),
            pytest.param(
                "/roled/",
                "get",
                "scope",
                False,
                403,
                "Insufficient roles",
                None,
                id="role_missing",
            ),
            pytest.param(
                "/roled/",
                "get",
                None,
                False,
                401,
                "Unauthorized",
                "Bearer",
                id="role_without_token",
            ),
            pytest.param("/both/", "get", "scope_and_role", False, 200, {"foo": "both"}, None, id="scope_and_role"),
            pytest.param(
                "/both/",
                "get",
                "role",
                False,
                403,
                "Insufficient permissions",
                'Bearer error="insufficient_scope", scope="flama.test.auth"',
                id="scope_and_role_without_scope",
            ),
            pytest.param("/resource/", "get", "audience", False, 200, {"foo": "resource"}, None, id="resource"),
            pytest.param(
                "/resource/",
                "get",
                "other_audience",
                False,
                401,
                f"Token not issued for '{RESOURCE}'",
                f'Bearer error="invalid_token", scope="flama.test.auth", resource_metadata="{METADATA}"',
                id="resource_other_audience",
            ),
            pytest.param(
                "/resource/",
                "get",
                None,
                False,
                401,
                "Unauthorized",
                f'Bearer scope="flama.test.auth", resource_metadata="{METADATA}"',
                id="resource_without_token",
            ),
            pytest.param(
                "/resource-only/",
                "get",
                "audience_only",
                False,
                200,
                {"foo": "resource-only"},
                None,
                id="resource_requiring_only_a_token",
            ),
            pytest.param(
                "/resource-only/",
                "get",
                None,
                False,
                401,
                "Unauthorized",
                f'Bearer resource_metadata="{METADATA}"',
                id="resource_requiring_only_a_token_without_token",
            ),
            pytest.param("/no-auth/", "get", "scope", False, 200, {"foo": "no-auth"}, None, id="no_auth_with_token"),
            pytest.param("/no-auth/", "get", None, False, 200, {"foo": "no-auth"}, None, id="no_auth_without_token"),
            pytest.param("/ignored/", "get", None, False, 200, {"foo": "ignored"}, None, id="ignored"),
            pytest.param(
                "/not-found/",
                "get",
                None,
                False,
                404,
                "Not Found",
                None,
                id="not_found",
            ),
            pytest.param(
                "/scoped/",
                "post",
                None,
                False,
                405,
                "Method Not Allowed",
                None,
                id="method_not_allowed",
            ),
        ),
    )
    async def test_request(self, client, secret, path, method, claims, cookie, status_code, result, challenge):
        if claims is not None:
            token = JWT({"alg": "HS256", "typ": "JWT"}, CLAIMS[claims]).encode(secret.bytes).decode()
            if cookie:
                client.cookies = {"access_token": token}
            else:
                client.headers = {"Authorization": f"Bearer {token}"}

        response = await client.request(method, path)

        assert response.status_code == status_code
        if status_code < 400:
            assert response.json() == result
        else:
            assert response.headers["content-type"] == "application/problem+json"
            assert response.json() == {
                "type": "about:blank",
                "title": HTTPStatus(status_code).phrase,
                "status": status_code,
                "detail": result,
            }
        assert response.headers.get("www-authenticate") == challenge

    async def test_request_challenges_an_invalid_token(self, client):
        client.headers = {"Authorization": f"Bearer {OUTAGE_TOKEN.decode()}"}

        response = await client.request("get", "/scoped/")

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Bearer error="invalid_token", scope="flama.test.auth"'

    async def test_request_keeps_the_headers_of_a_refusal(self):
        def resolver(kid):
            raise KeysUnavailable(retry_after=2.5)

        app = Flama(
            schema=None,
            docs=None,
            components=[AccessTokenComponent(resolver=resolver)],
            middleware=[AuthenticationMiddleware()],
        )

        @app.route("/auth/", tags={"permissions": ["flama.test.auth"]})
        def auth():
            return {"foo": "auth"}

        async with Client(app=app) as client:
            client.headers = {"Authorization": f"Bearer {OUTAGE_TOKEN.decode()}"}
            response = await client.get("/auth/")

        assert response.status_code == 503
        assert response.headers["retry-after"] == "3"
