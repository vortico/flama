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


# Deliberately not an ``Unauthorized``: being unable to look a key up says nothing about the token presented,
# so it must not be reported to the caller as a rejected one.
class KeysUnavailable(AuthenticationException): ...


class JWTException(AuthenticationException): ...


class JWTDecodeException(JWTException, SignatureDecodeException): ...


class JWTValidateException(JWTException, SignatureVerificationException): ...


class JWTClaimValidateException(JWTValidateException):
    def __init__(self, claim: str) -> None:
        self.claim = claim
        super().__init__(f"Claim '{self.claim}' is not valid")
