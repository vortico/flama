import http
import logging

from flama import Component
from flama.authentication import exceptions, jwt
from flama.exceptions import HTTPException
from flama.types import Headers
from flama.types.http import Cookies

logger = logging.getLogger(__name__)

__all__ = ["JWTComponent"]


class JWTComponent(Component):
    def __init__(
        self,
        secret: bytes,
        *,
        header_key: str = "Authorization",
        header_prefix: str = "Bearer",
        cookie_key: str = "flama_authentication",
    ):
        self.secret = secret
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

    def resolve(self, headers: Headers, cookies: Cookies) -> jwt.JWT:
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
            token = jwt.JWT.decode(encoded_token, self.secret)
        except (exceptions.JWTDecodeException, exceptions.JWTValidateException) as e:
            raise HTTPException(
                status_code=http.HTTPStatus.UNAUTHORIZED, detail={"error": e.__class__, "description": str(e)}
            )

        return token
