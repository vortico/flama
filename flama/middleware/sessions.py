import hashlib
import time
import typing as t

from flama import concurrency, types
from flama.crypto import JWS
from flama.crypto.exceptions import SignatureDecodeException, SignatureVerificationException
from flama.http.data_structures import MutableHeaders
from flama.http.requests.connection import HTTPConnection
from flama.middleware.base import Middleware

__all__ = ["SessionMiddleware"]


class SessionMiddleware(Middleware):
    """ASGI middleware providing signed cookie-based sessions.

    Session data is serialised to JSON, signed as a JWS token with HMAC-SHA256 and stored in a cookie.  Expiration is
    enforced via the ``iat`` (issued-at) claim embedded in the payload.

    :param secret_key: Secret used to sign the session cookie.
    :param session_cookie: Name of the session cookie.
    :param max_age: Maximum cookie age in seconds. ``None`` for session cookies.
    :param path: Cookie path.
    :param same_site: ``SameSite`` cookie attribute.
    :param https_only: Whether to set the ``Secure`` flag.
    :param domain: Cookie domain.
    """

    def __init__(
        self,
        secret_key: bytes,
        session_cookie: str = "session",
        max_age: int | None = 14 * 24 * 60 * 60,
        path: str = "/",
        same_site: t.Literal["lax", "strict", "none"] = "lax",
        https_only: bool = False,
        domain: str | None = None,
    ) -> None:
        self._key = hashlib.sha256(secret_key).digest()
        self._session_cookie = session_cookie
        self._max_age = max_age
        self._path = path

        flags = ["httponly", f"samesite={same_site}"]
        if https_only:
            flags.append("secure")
        if domain is not None:
            flags.append(f"domain={domain}")
        self._security_flags = "; ".join(flags)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await concurrency.run(self.app, scope, receive, send)
            return

        connection = HTTPConnection(scope)
        initial_session_was_empty = True

        if self._session_cookie in connection.cookies:
            try:
                scope["session"] = self._decode_session(connection.cookies[self._session_cookie].encode())
                initial_session_was_empty = False
            except (SignatureDecodeException, SignatureVerificationException, ValueError):
                scope["session"] = {}
        else:
            scope["session"] = {}

        async def _send(message: types.Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if scope["session"]:
                    headers.append(
                        "set-cookie",
                        "; ".join(
                            [
                                f"{self._session_cookie}={self._encode_session(scope['session']).decode()}",
                                f"path={self._path}",
                                f"Max-Age={str(self._max_age)}" if self._max_age else "",
                                f"{self._security_flags}",
                            ]
                        ),
                    )
                elif not initial_session_was_empty:
                    headers.append(
                        "set-cookie",
                        "; ".join(
                            [
                                f"{self._session_cookie}=null",
                                f"path={self._path}",
                                "expires=Thu, 01 Jan 1970 00:00:00 GMT",
                                f"{self._security_flags}",
                            ]
                        ),
                    )
            await send(message)

        await concurrency.run(self.app, scope, receive, _send)

    def _encode_session(self, data: dict[str, t.Any]) -> bytes:
        """Sign session data as a JWS token.

        :param data: Session dictionary.
        :return: JWS token bytes.
        """
        return JWS.encode(header={"alg": "HS256"}, payload={"data": data, "iat": int(time.time())}, key=self._key)

    def _decode_session(self, token: bytes) -> dict[str, t.Any]:
        """Verify and decode a JWS session token.

        :param token: Raw cookie value.
        :return: Session dictionary.
        :raises SignatureDecodeException: If the token is malformed.
        :raises SignatureVerificationException: If the signature is invalid.
        :raises ValueError: If the session has expired.
        """
        _, payload, _ = JWS.decode(token, self._key)

        if self._max_age is not None:
            iat = payload.get("iat", 0)
            if time.time() - iat > self._max_age:
                raise ValueError("Session expired")

        return payload.get("data", {})
