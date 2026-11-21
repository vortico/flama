import http
import math
import typing as t

from flama.crypto.exceptions import SignatureDecodeException, SignatureVerificationException

__all__ = [
    "AuthenticationException",
    "Unauthorized",
    "AuthenticationError",
    "MissingToken",
    "MalformedToken",
    "InvalidToken",
    "InsufficientScope",
    "InsufficientRoles",
    "KeysUnavailable",
    "JWTException",
    "JWTDecodeException",
    "JWTValidateException",
    "JWTClaimValidateException",
]


class AuthenticationException(Exception): ...


class Unauthorized(AuthenticationException): ...


class Forbidden(AuthenticationException): ...


class AuthenticationError(AuthenticationException):
    """A request refused for the credentials it carries or for what they grant.

    It is answered with its status and, when it challenges the client, a ``WWW-Authenticate`` challenge (RFC 6750)
    naming its error, the scopes required and the metadata of the protected resource the request was for (RFC 9728).

    :param detail: Human-readable explanation, the status phrase by default.
    :param scheme: Authentication scheme of the challenge.
    :param scopes: Scopes required, which the challenge lists.
    :param resource_metadata: URL of the metadata of the protected resource, which the challenge points at.
    """

    status_code: t.ClassVar[int] = http.HTTPStatus.UNAUTHORIZED
    error: t.ClassVar[str | None] = None
    challenges: t.ClassVar[bool] = True

    def __init__(
        self,
        detail: str | None = None,
        *,
        scheme: str = "Bearer",
        scopes: t.Iterable[str] = (),
        resource_metadata: str | None = None,
    ) -> None:
        self.detail = detail if detail is not None else http.HTTPStatus(self.status_code).phrase
        self.scheme = scheme
        self.scopes = set(scopes)
        self.resource_metadata = resource_metadata
        super().__init__(self.detail)

    @property
    def headers(self) -> dict[str, str]:
        """Headers of the response, carrying the challenge if any."""
        if not self.challenges:
            return {}

        params = [
            *([f'error="{self.error}"'] if self.error else []),
            *([f'scope="{" ".join(sorted(self.scopes))}"'] if self.scopes else []),
            *([f'resource_metadata="{self.resource_metadata}"'] if self.resource_metadata else []),
        ]
        return {"WWW-Authenticate": f"{self.scheme} {', '.join(params)}" if params else self.scheme}

    def __str__(self) -> str:
        return self.detail


class MissingToken(AuthenticationError):
    """A request carrying no token for a resource that requires one."""


class MalformedToken(AuthenticationError):
    """A request carrying its token in a form it cannot be read in."""

    status_code = http.HTTPStatus.BAD_REQUEST
    error = "invalid_request"


class InvalidToken(AuthenticationError):
    """A request carrying a token that cannot be decoded, is not valid, or was not issued for its resource."""

    error = "invalid_token"


class InsufficientScope(AuthenticationError):
    """A request whose token lacks scopes its resource requires."""

    status_code = http.HTTPStatus.FORBIDDEN
    error = "insufficient_scope"


class InsufficientRoles(AuthenticationError):
    """A request whose principal lacks roles its resource requires, which no other token can solve."""

    status_code = http.HTTPStatus.FORBIDDEN
    challenges = False


class KeysUnavailable(AuthenticationError):
    """The key a token names cannot be checked right now.

    :param detail: Human-readable explanation.
    :param retry_after: Seconds until checking again is worthwhile, if known.
    """

    status_code = http.HTTPStatus.SERVICE_UNAVAILABLE
    challenges = False

    def __init__(self, detail: str | None = None, *, retry_after: float | None = None, **kwargs: t.Any) -> None:
        super().__init__(detail, **kwargs)
        self.retry_after = retry_after

    @property
    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(max(0, math.ceil(self.retry_after)))} if self.retry_after is not None else {}


class JWTException(AuthenticationException): ...


class JWTDecodeException(JWTException, SignatureDecodeException): ...


class JWTValidateException(JWTException, SignatureVerificationException): ...


class JWTClaimValidateException(JWTValidateException):
    def __init__(self, claim: str) -> None:
        self.claim = claim
        super().__init__(f"Claim '{self.claim}' is not valid")
