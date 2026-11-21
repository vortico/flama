import json

import pytest

from flama.authentication import exceptions
from flama.authentication.exception_handlers import AuthenticationExceptionHandler


class TestCaseAuthenticationExceptionHandler:
    @pytest.mark.parametrize(
        ["exc", "status_code", "title", "headers"],
        (
            pytest.param(
                exceptions.InvalidToken("Expired", scopes=["a"]),
                401,
                "Unauthorized",
                {"www-authenticate": 'Bearer error="invalid_token", scope="a"'},
                id="challenge",
            ),
            pytest.param(
                exceptions.KeysUnavailable("Down", retry_after=1),
                503,
                "Service Unavailable",
                {"retry-after": "1"},
                id="retry",
            ),
        ),
    )
    async def test_authentication_error(self, asgi_scope, asgi_receive, asgi_send, exc, status_code, title, headers):
        response = await AuthenticationExceptionHandler()(asgi_scope, asgi_receive, asgi_send, exc)

        assert response.status_code == status_code
        assert response.headers["content-type"] == "application/problem+json"
        assert {k: v for k, v in response.headers.items() if k in headers} == headers
        assert json.loads(response.body) == {
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "detail": exc.detail,
        }

    async def test_unhandled(self, asgi_scope, asgi_receive, asgi_send):
        with pytest.raises(exceptions.JWTException):
            await AuthenticationExceptionHandler()(asgi_scope, asgi_receive, asgi_send, exceptions.JWTException())
