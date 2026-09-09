import typing as t

from flama.authentication.jwt import JWT

__all__ = ["AccessToken", "RefreshToken", "KeyResolver"]

# Looks a key up by the identity a token's header gives it, which may mean reaching across the network, so the
# result may be awaited. Raising ``Unauthorized`` says no key answers to that identity; any other exception is
# a failure of the lookup itself.
KeyResolver = t.Callable[[str | None], bytes] | t.Callable[[str | None], t.Awaitable[bytes]]


class AccessToken(JWT): ...


class RefreshToken(JWT): ...
