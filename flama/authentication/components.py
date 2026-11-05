import http
import logging
import math
import typing as t
import warnings

from flama import Component, _concurrency
from flama.authentication import exceptions, jwt, types
from flama.crypto import JWS
from flama.crypto.exceptions import SignatureDecodeException
from flama.exceptions import HTTPException
from flama.http.data_structures import Headers
from flama.types.http import Cookies

T = t.TypeVar("T", bound=jwt.JWT)

__all__ = ["AccessTokenComponent", "RefreshTokenComponent"]

logger = logging.getLogger(__name__)


class BaseTokenComponent(Component):
    def __init__(
        self,
        secret: bytes | None = None,
        *,
        secret_resolver: types.KeyResolver | None = None,
        header_key: str,
        header_prefix: str,
        cookie_key: str,
        legacy_header_key: str | None = None,
    ):
        if (secret is None) == (secret_resolver is None):
            raise ValueError("Give either a secret or a resolver, not both and not neither")

        self.secret = secret
        self.secret_resolver = secret_resolver
        self.header_key = header_key
        self.header_prefix = header_prefix
        self.cookie_key = cookie_key
        self.legacy_header_key = legacy_header_key

    def _token_from_cookies(self, cookies: Cookies) -> bytes:
        try:
            token = cookies[self.cookie_key]["value"]
        except KeyError:
            logger.debug("'%s' not found in cookies", self.cookie_key)
            raise exceptions.Unauthorized()

        return token.encode()

    def _token_from_header(self, headers: Headers) -> bytes:
        if self.header_key in headers:
            value = headers[self.header_key]
        elif self.legacy_header_key is not None and self.legacy_header_key in headers:
            warnings.warn(
                f"Sending the token in the '{self.legacy_header_key}' header is deprecated and will be removed in "
                f"Flama 3.0, use '{self.header_key}' instead",
                DeprecationWarning,
                stacklevel=2,
            )
            value = headers[self.legacy_header_key]
        else:
            logger.debug("'%s' not found in headers", self.header_key)
            raise exceptions.Unauthorized()

        try:
            header_prefix, token = value.split()
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

    async def _resolve_token(self, token_cls: type[T], headers: Headers, cookies: Cookies, /) -> T:
        try:
            try:
                encoded_token = self._token_from_header(headers)
            except exceptions.Unauthorized:
                encoded_token = self._token_from_cookies(cookies)
        except exceptions.Unauthorized:
            raise HTTPException(
                status_code=http.HTTPStatus.UNAUTHORIZED, headers={"WWW-Authenticate": self.header_prefix}
            )
        except exceptions.JWTException as e:
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST,
                detail={"error": e.__class__, "description": str(e)},
                headers={"WWW-Authenticate": f'{self.header_prefix} error="invalid_request"'},
            )

        try:
            if self.secret_resolver is not None:
                key = await _concurrency.run(self.secret_resolver, JWS.header(encoded_token).get("kid"))
            else:
                key = t.cast(bytes, self.secret)

            token = token_cls.decode(encoded_token, key)
        except (
            exceptions.Unauthorized,
            SignatureDecodeException,
            exceptions.JWTDecodeException,
            exceptions.JWTValidateException,
        ) as e:
            raise HTTPException(
                status_code=http.HTTPStatus.UNAUTHORIZED,
                detail={"error": e.__class__, "description": str(e)},
                headers={"WWW-Authenticate": f'{self.header_prefix} error="invalid_token"'},
            )
        except exceptions.KeysUnavailable as e:
            raise HTTPException(
                status_code=http.HTTPStatus.SERVICE_UNAVAILABLE,
                detail={"error": e.__class__, "description": str(e)},
                headers={"Retry-After": str(max(0, math.ceil(e.retry_after)))} if e.retry_after is not None else None,
            )

        return token


class AccessTokenComponent(BaseTokenComponent):
    """Inject the access token of a request, read from its ``Authorization`` header or its cookie.

    .. deprecated::
        With the default header, a token in the ``access_token`` header used before 2.3 is still accepted. It will
        stop being read in Flama 3.0.

    :param secret: Key to verify tokens with.
    :param resolver: Resolver of the key each token names, instead of a single ``secret``.
    :param header_prefix: Authentication scheme preceding the token in the header.
    :param header_key: Header to read the token from, ``Authorization`` if not given.
    :param cookie_key: Cookie to read the token from.
    """

    LEGACY_HEADER_KEY: t.ClassVar[str] = "access_token"

    def __init__(
        self,
        secret: bytes | None = None,
        *,
        resolver: types.KeyResolver | None = None,
        header_prefix: str = "Bearer",
        header_key: str | None = None,
        cookie_key: str = "access_token",
    ):
        super().__init__(
            secret,
            secret_resolver=resolver,
            header_prefix=header_prefix,
            header_key=header_key if header_key is not None else "Authorization",
            cookie_key=cookie_key,
            legacy_header_key=self.LEGACY_HEADER_KEY if header_key is None else None,
        )

    async def resolve(self, headers: Headers, cookies: Cookies) -> types.AccessToken:
        return await self._resolve_token(types.AccessToken, headers, cookies)


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
        return await self._resolve_token(types.RefreshToken, headers, cookies)
