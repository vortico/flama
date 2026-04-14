from flama.crypto.exceptions import SignatureDecodeException, SignatureVerificationException

__all__ = [
    "AuthenticationException",
    "Unauthorized",
    "JWTException",
    "JWTDecodeException",
    "JWTValidateException",
    "JWTClaimValidateException",
]


class AuthenticationException(Exception): ...


class Unauthorized(AuthenticationException): ...


class Forbidden(AuthenticationException): ...


class JWTException(AuthenticationException): ...


class JWTDecodeException(JWTException, SignatureDecodeException): ...


class JWTValidateException(JWTException, SignatureVerificationException): ...


class JWTClaimValidateException(JWTValidateException):
    def __init__(self, claim: str) -> None:
        self.claim = claim
        super().__init__(f"Claim '{self.claim}' is not valid")
