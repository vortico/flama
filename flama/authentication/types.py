import typing as t

from flama.authentication.jwt import JWT

__all__ = ["AccessToken", "RefreshToken"]

AccessToken = t.NewType("AccessToken", JWT)
RefreshToken = t.NewType("RefreshToken", JWT)
