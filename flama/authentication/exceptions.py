__all__ = [
    "AuthenticationException",
    "Unauthorized",
    "JWTException",
    "JWTDecodeException",
    "JWTValidateException",
    "JWTClaimValidateException",
]


class AuthenticationException(Exception):
    ...


class Unauthorized(AuthenticationException):
    ...


class Forbidden(AuthenticationException):
    ...


class JWTException(AuthenticationException):
    ...


class JWTDecodeException(JWTException):
    ...


class JWTValidateException(JWTException):
    ...


class JWTClaimValidateException(JWTValidateException):
    def __init__(self, claim: str) -> None:
        self.claim = claim
        super().__init__(f"Claim '{self.claim}' is not valid")
