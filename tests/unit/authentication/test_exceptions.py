import pytest

from flama.authentication import exceptions


class TestCaseAuthenticationError:
    @pytest.mark.parametrize(
        ["exc", "status_code", "detail", "headers"],
        (
            pytest.param(exceptions.MissingToken(), 401, "Unauthorized", {"WWW-Authenticate": "Bearer"}, id="missing"),
            pytest.param(
                exceptions.MalformedToken("Wrong header", scheme="Token"),
                400,
                "Wrong header",
                {"WWW-Authenticate": 'Token error="invalid_request"'},
                id="malformed",
            ),
            pytest.param(
                exceptions.InvalidToken(scopes=["b", "a"], resource_metadata="https://example.com/.well-known/r"),
                401,
                "Unauthorized",
                {
                    "WWW-Authenticate": (
                        'Bearer error="invalid_token", scope="a b", resource_metadata="https://example.com/.well-known/r"'
                    )
                },
                id="invalid",
            ),
            pytest.param(
                exceptions.InsufficientScope(scopes=["a"]),
                403,
                "Forbidden",
                {"WWW-Authenticate": 'Bearer error="insufficient_scope", scope="a"'},
                id="insufficient_scope",
            ),
            pytest.param(exceptions.InsufficientRoles("Insufficient roles"), 403, "Insufficient roles", {}, id="roles"),
            pytest.param(exceptions.KeysUnavailable(), 503, "Service Unavailable", {}, id="keys_unavailable"),
            pytest.param(
                exceptions.KeysUnavailable("Down", retry_after=2.5),
                503,
                "Down",
                {"Retry-After": "3"},
                id="keys_unavailable_retry",
            ),
            pytest.param(
                exceptions.KeysUnavailable(retry_after=-1), 503, "Service Unavailable", {"Retry-After": "0"}, id="past"
            ),
        ),
    )
    def test_error(self, exc, status_code, detail, headers):
        assert exc.status_code == status_code
        assert exc.detail == detail
        assert str(exc) == detail
        assert exc.headers == headers
