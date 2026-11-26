import contextlib
import contextvars
import hashlib
import hmac
import json
import secrets
import typing as t

if t.TYPE_CHECKING:
    from flama.http.requests import Request

__all__ = [
    "CACHE_PARAM_NAMES",
    "CacheIsolation",
    "cache_context",
    "cache_secret",
    "current_cache_identity",
    "request_cache_identity",
    "request_cache_context",
    "validate_cache_isolation",
]

CacheIsolation = t.Literal["shared", "tenant", "user"]
_UNSET = object()
_CACHE_IDENTITY: contextvars.ContextVar[object] = contextvars.ContextVar("flama_llm_cache_identity", default=_UNSET)
CACHE_PARAM_NAMES: t.Final[frozenset[str]] = frozenset(
    {"cache_salt", "prompt_cache_salt", "prompt_cache_key", "prompt_cache", "cache_key"}
)


def validate_cache_isolation(value: str, /) -> CacheIsolation:
    if value not in t.get_args(CacheIsolation):
        raise ValueError(f"cache_isolation must be one of {', '.join(t.get_args(CacheIsolation))}")
    return t.cast(CacheIsolation, value)


def cache_secret(value: bytes | str | None = None, /) -> bytes:
    if value is None:
        return secrets.token_bytes(32)
    secret = value.encode() if isinstance(value, str) else value
    if not isinstance(secret, bytes) or not secret:
        raise ValueError("cache_secret must be a non-empty bytes or string value")
    return secret


def current_cache_identity() -> object:
    """Return the request identity, ``None`` for explicit shared scope, or an unset sentinel."""
    return _CACHE_IDENTITY.get()


@contextlib.contextmanager
def cache_context(identity: str | None) -> t.Iterator[None]:
    token = _CACHE_IDENTITY.set(identity)
    try:
        yield
    finally:
        _CACHE_IDENTITY.reset(token)


def _stable_claim(value: t.Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (str, int, float)):
        return str(value)
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return str(value)


def _user_claim(token: t.Any) -> str:
    payload = token.payload
    if payload.sub is not None:
        issuer = payload.iss or ""
        return f"subject:{issuer}:{payload.sub}"

    data = payload.data if isinstance(payload.data, dict) else {}
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return f"data:{encoded}"


def _tenant_claim(token: t.Any) -> str:
    data = token.payload.data if isinstance(token.payload.data, dict) else {}
    for key in ("tenant_id", "tenant", "organization_id", "organization", "org_id", "org"):
        value = _stable_claim(data.get(key))
        if value is not None:
            issuer = token.payload.iss or ""
            return f"tenant:{issuer}:{value}"
    return _user_claim(token)


async def _authenticated_claim(request: "Request") -> tuple[str, t.Any] | None:
    try:
        from flama import authentication
        from flama.context import Context

        token = await request.app.injector.value(authentication.AccessToken, Context(request=request))
    except Exception:
        return None
    return "authenticated", token


async def request_cache_identity(request: "Request", *, isolation: CacheIsolation, secret: bytes) -> str | None:
    """Derive an opaque, server-controlled cache identity for one HTTP request."""
    if isolation == "shared":
        return None

    authenticated = await _authenticated_claim(request)
    if authenticated is None:
        return None
    _, token = authenticated
    claim = _tenant_claim(token) if isolation == "tenant" else _user_claim(token)
    return hmac.new(secret, f"flama-prompt-cache:{isolation}:{claim}".encode(), hashlib.sha256).hexdigest()


@contextlib.asynccontextmanager
async def request_cache_context(model: t.Any, request: "Request") -> t.AsyncIterator[None]:
    isolation = getattr(model, "cache_isolation", "user")
    if not isinstance(isolation, str):
        isolation = "user"
    isolation = validate_cache_isolation(isolation)
    secret = getattr(model, "cache_secret", None)
    if not isinstance(secret, bytes):
        secret = cache_secret(secret if isinstance(secret, str) else None)
    identity = await request_cache_identity(request, isolation=isolation, secret=secret)
    with cache_context(identity):
        yield
