import typing as t

from flama.crypto.exceptions import SignatureDecodeException, SignatureVerificationException

__all__ = [
    "AuthenticationException",
    "Unauthorized",
    "KeysUnavailable",
    "JWTException",
    "JWTDecodeException",
    "JWTValidateException",
    "JWTClaimValidateException",
]


class AuthenticationException(Exception): ...


class Unauthorized(AuthenticationException): ...


class Forbidden(AuthenticationException): ...


class KeysUnavailable(AuthenticationException):
    """The key a token names cannot be checked right now.

    :param retry_after: Seconds until checking again is worthwhile, if known.
    """

    def __init__(self, *args: t.Any, retry_after: float | None = None) -> None:
        super().__init__(*args)
        self.retry_after = retry_after


class JWTException(AuthenticationException): ...


class JWTDecodeException(JWTException, SignatureDecodeException): ...


class JWTValidateException(JWTException, SignatureVerificationException): ...


class JWTClaimValidateException(JWTValidateException):
    def __init__(self, claim: str) -> None:
        self.claim = claim
        super().__init__(f"Claim '{self.claim}' is not valid")
