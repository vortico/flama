import logging
import typing as t

from flama import Component, Components, _concurrency
from flama.authentication import exceptions, jwt, types
from flama.authentication.data_structures import Principal
from flama.crypto import JWS
from flama.crypto.exceptions import SignatureDecodeException
from flama.http.data_structures import Headers
from flama.injection.exceptions import ValueNotFound
from flama.types.http import Cookies

T = t.TypeVar("T", bound=jwt.JWT)

__all__ = ["AccessTokenComponent", "RefreshTokenComponent", "PrincipalComponent", "AUTHENTICATION_COMPONENTS"]

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
        audience: str | None = None,
    ):
        if (secret is None) == (secret_resolver is None):
            raise ValueError("Give either a secret or a resolver, not both and not neither")

        self.secret = secret
        self.secret_resolver = secret_resolver
        self.header_key = header_key
        self.header_prefix = header_prefix
        self.cookie_key = cookie_key
        self.audience = audience

    def _token_from_cookies(self, cookies: Cookies) -> bytes:
        try:
            token = cookies[self.cookie_key]["value"]
        except KeyError:
            logger.debug("'%s' not found in cookies", self.cookie_key)
            raise exceptions.Unauthorized()

        return token.encode()

    def _token_from_header(self, headers: Headers) -> bytes:
        try:
            value = headers[self.header_key]
        except KeyError:
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
            raise ValueNotFound(exceptions.MissingToken(scheme=self.header_prefix))
        except exceptions.JWTException as e:
            raise exceptions.MalformedToken(str(e), scheme=self.header_prefix) from e

        try:
            if self.secret_resolver is not None:
                key = await _concurrency.run(self.secret_resolver, JWS.header(encoded_token).get("kid"))
            else:
                key = t.cast(bytes, self.secret)

            token = token_cls.decode(encoded_token, key, aud=self.audience)
        except (
            exceptions.Unauthorized,
            SignatureDecodeException,
            exceptions.JWTDecodeException,
            exceptions.JWTValidateException,
        ) as e:
            raise exceptions.InvalidToken(str(e), scheme=self.header_prefix) from e

        return token


class AccessTokenComponent(BaseTokenComponent):
    """Inject the access token of a request, read from its ``Authorization`` header or its cookie.

    A parameter with a default, as ``token: AccessToken | None = None``, receives it when the request carries no token,
    while a malformed or invalid token is refused all the same.

    :param secret: Key to verify tokens with.
    :param resolver: Resolver of the key each token names, instead of a single ``secret``.
    :param header_prefix: Authentication scheme preceding the token in the header.
    :param header_key: Header to read the token from.
    :param cookie_key: Cookie to read the token from.
    :param audience: Audience a token must be issued for, so tokens issued for other services are refused. Any
        audience is accepted if not given.
    """

    def __init__(
        self,
        secret: bytes | None = None,
        *,
        resolver: types.KeyResolver | None = None,
        header_prefix: str = "Bearer",
        header_key: str = "Authorization",
        cookie_key: str = "access_token",
        audience: str | None = None,
    ):
        super().__init__(
            secret,
            secret_resolver=resolver,
            header_prefix=header_prefix,
            header_key=header_key,
            cookie_key=cookie_key,
            audience=audience,
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


class PrincipalComponent(Component):
    """Inject the :class:`Principal` a request acts for, read from its access token.

    A request carrying no token is refused, unless the parameter has a default, as in
    ``principal: Principal | None = None``, which it receives instead. A claim holds a space-separated string, as
    ``scope`` does (RFC 8693), or a list of names, as ``roles`` does (RFC 9068); either shape is read from either claim,
    so providers listing their scopes, as ``scp`` does, are read alike. Register one with other claims to replace the
    default.

    :param scope_claim: Claim the scopes are read from.
    :param roles_claim: Claim the roles are read from.
    """

    def __init__(self, *, scope_claim: str = "scope", roles_claim: str = "roles") -> None:
        self.scope_claim = scope_claim
        self.roles_claim = roles_claim

    def resolve(self, token: types.AccessToken) -> Principal:
        claims = token.payload.data
        return Principal(
            subject=token.payload.sub,
            scopes=self._values(claims.get(self.scope_claim)),
            roles=self._values(claims.get(self.roles_claim)),
        )

    @staticmethod
    def _values(claim: t.Any) -> frozenset[str]:
        """The names a claim holds, from a space-separated string or a list.

        :param claim: Value of the claim.
        :return: The names, none for a missing or unreadable claim.
        """
        if isinstance(claim, str):
            return frozenset(claim.split())

        if isinstance(claim, list | tuple):
            return frozenset(str(x) for x in claim)

        return frozenset()


AUTHENTICATION_COMPONENTS = Components([PrincipalComponent()])
