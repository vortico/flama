from flama.authentication.jwt import JWT

__all__ = ["AccessToken", "RefreshToken"]


class AccessToken(JWT): ...


class RefreshToken(JWT): ...
