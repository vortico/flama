import types
from unittest.mock import AsyncMock

import pytest

from flama.authentication.types import AccessToken
from flama.models.cache import (
    _UNSET,
    cache_context,
    current_cache_identity,
    request_cache_context,
    request_cache_identity,
    validate_cache_isolation,
)


def _request(token: AccessToken | Exception | None) -> types.SimpleNamespace:
    injector = types.SimpleNamespace()
    if isinstance(token, Exception):
        injector.value = AsyncMock(side_effect=token)
    else:
        injector.value = AsyncMock(return_value=token)
    return types.SimpleNamespace(app=types.SimpleNamespace(injector=injector))


def _token(*, subject: str | None = None, tenant: str | None = None) -> AccessToken:
    data = {"tenant_id": tenant} if tenant is not None else {}
    return AccessToken(_payload={"iss": "issuer", "sub": subject, "data": data})


class TestCaseCacheIdentity:
    async def test_user_scope_is_stable_opaque_and_separates_subjects(self) -> None:
        request_a = _request(_token(subject="alice"))
        request_b = _request(_token(subject="bob"))

        alice = await request_cache_identity(request_a, isolation="user", secret=b"server-secret")
        same_alice = await request_cache_identity(request_a, isolation="user", secret=b"server-secret")
        bob = await request_cache_identity(request_b, isolation="user", secret=b"server-secret")

        assert alice == same_alice
        assert alice != bob
        assert alice is not None
        assert "alice" not in alice
        assert "issuer" not in alice

    async def test_tenant_scope_groups_subjects_within_tenant(self) -> None:
        tenant_a_user_1 = await request_cache_identity(
            _request(_token(subject="alice", tenant="tenant-a")), isolation="tenant", secret=b"secret"
        )
        tenant_a_user_2 = await request_cache_identity(
            _request(_token(subject="bob", tenant="tenant-a")), isolation="tenant", secret=b"secret"
        )
        tenant_b_user = await request_cache_identity(
            _request(_token(subject="alice", tenant="tenant-b")), isolation="tenant", secret=b"secret"
        )

        assert tenant_a_user_1 == tenant_a_user_2
        assert tenant_a_user_1 != tenant_b_user

    @pytest.mark.parametrize("isolation", ["shared", "user", "tenant"])
    async def test_missing_authentication_falls_back_to_shared_scope(self, isolation: str) -> None:
        identity = await request_cache_identity(
            _request(RuntimeError("authentication unavailable")), isolation=isolation, secret=b"secret"
        )

        assert identity is None

    async def test_shared_scope_does_not_resolve_authentication(self) -> None:
        request = _request(_token(subject="alice"))

        assert await request_cache_identity(request, isolation="shared", secret=b"secret") is None
        request.app.injector.value.assert_not_awaited()

    async def test_request_context_is_scoped_and_ignores_client_fields(self) -> None:
        request = _request(_token(subject="alice"))
        request.cache_salt = "client-controlled"
        model = types.SimpleNamespace(cache_isolation="user", cache_secret=b"server-secret")

        assert current_cache_identity() is _UNSET
        async with request_cache_context(model, request):
            identity = current_cache_identity()
            assert isinstance(identity, str)
            assert identity != request.cache_salt
        assert current_cache_identity() is _UNSET

    def test_invalid_isolation_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="cache_isolation"):
            validate_cache_isolation("account")

    def test_cache_context_restores_previous_identity(self) -> None:
        with cache_context("outer"):
            with cache_context("inner"):
                assert current_cache_identity() == "inner"
            assert current_cache_identity() == "outer"
        assert current_cache_identity() is _UNSET
