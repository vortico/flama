from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    BaseUser,
    SimpleUser,
    UnauthenticatedUser,
    has_required_scope,
    requires,
)

__all__ = [
    "has_required_scope",
    "requires",
    "AuthenticationError",
    "AuthenticationBackend",
    "AuthCredentials",
    "BaseUser",
    "SimpleUser",
    "UnauthenticatedUser",
]
