import http
import logging
import typing as t

from flama import Component, concurrency
from flama.authentication import exceptions, jwt, types
from flama.crypto import JWS
from flama.crypto.exceptions import SignatureDecodeException
from flama.exceptions import HTTPException
from flama.http.data_structures import Headers
from flama.types.http import Cookies

logger = logging.getLogger(__name__)

__all__ = ["AccessTokenComponent", "RefreshTokenComponent"]


class BaseTokenComponent(Component):
    def __init__(
        self,
        secret: bytes | None = None,
        *,
        secret_resolver: types.KeyResolver | None = None,
        header_key: str,
        header_prefix: str,
        cookie_key: str,
    ):
        if (secret is None) == (secret_resolver is None):
            raise ValueError("Give either a secret or a resolver, not both and not neither")

        self.secret = secret
        self.secret_resolver = secret_resolver
        self.header_key = header_key
        self.header_prefix = header_prefix
        self.cookie_key = cookie_key

    def _token_from_cookies(self, cookies: Cookies) -> bytes:
        try:
            token = cookies[self.cookie_key]["value"]
        except KeyError:
            logger.debug("'%s' not found in cookies", self.cookie_key)
            raise exceptions.Unauthorized()

        return token.encode()

    def _token_from_header(self, headers: Headers) -> bytes:
        try:
            header_prefix, token = headers[self.header_key].split()
        except KeyError:
            logger.debug("'%s' not found in headers", self.header_key)
            raise exceptions.Unauthorized()
        except ValueError:
            logger.debug("Wrong format for authorization header value")
            raise exceptions.JWTException(
                f"Authentication header must be '{self.header_key}: {self.header_prefix} <token>'"
            )

        if header_prefix != self.header_prefix:
            logger.debug("Wrong prefix '%s' for authorization header, expected '%s'", header_prefix, self.header_prefix)
            raise exceptions.JWTException(
                f"Authentication header must be '{self.header_key}: {self.header_prefix} <token>'"
            )

        return token.encode()

    async def _resolve_token(self, headers: Headers, cookies: Cookies) -> jwt.JWT:
        try:
            try:
                encoded_token = self._token_from_header(headers)
            except exceptions.Unauthorized:
                encoded_token = self._token_from_cookies(cookies)
        except exceptions.Unauthorized:
            raise HTTPException(status_code=http.HTTPStatus.UNAUTHORIZED)
        except exceptions.JWTException as e:
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST, detail={"error": e.__class__, "description": str(e)}
            )

        try:
            if self.secret_resolver is not None:
                key = await concurrency.run(self.secret_resolver, JWS.header(encoded_token).get("kid"))
            else:
                key = t.cast(bytes, self.secret)

            token = jwt.JWT.decode(encoded_token, key)
        except (
            exceptions.Unauthorized,
            SignatureDecodeException,
            exceptions.JWTDecodeException,
            exceptions.JWTValidateException,
        ) as e:
            raise HTTPException(
                status_code=http.HTTPStatus.UNAUTHORIZED, detail={"error": e.__class__, "description": str(e)}
            )

        return token


class AccessTokenComponent(BaseTokenComponent):
    def __init__(
        self,
        secret: bytes | None = None,
        *,
        resolver: types.KeyResolver | None = None,
        header_prefix: str = "Bearer",
        header_key: str = "access_token",
        cookie_key: str = "access_token",
    ):
        super().__init__(
            secret,
            secret_resolver=resolver,
            header_prefix=header_prefix,
            header_key=header_key,
            cookie_key=cookie_key,
        )

    async def resolve(self, headers: Headers, cookies: Cookies) -> types.AccessToken:
        token = await self._resolve_token(headers, cookies)
        return types.AccessToken(token.header, token.payload)


class RefreshTokenComponent(BaseTokenComponent):
    def __init__(
        self,
        secret: bytes | None = None,
        *,
        resolver: types.KeyResolver | None = None,
        header_prefix: str = "Bearer",
        header_key: str = "refresh_token",
        cookie_key: str = "refresh_token",
    ):
        super().__init__(
            secret,
            secret_resolver=resolver,
            header_prefix=header_prefix,
            header_key=header_key,
            cookie_key=cookie_key,
        )

    async def resolve(self, headers: Headers, cookies: Cookies) -> types.RefreshToken:
        token = await self._resolve_token(headers, cookies)
        return types.RefreshToken(token.header, token.payload)
