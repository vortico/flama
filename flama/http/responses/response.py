import http.cookies
import sys
import typing as t
from datetime import datetime

from flama import types
from flama.http.data_structures import MutableHeaders

if t.TYPE_CHECKING:
    from collections.abc import Mapping

    from flama.background import BackgroundTask

__all__ = ["Response"]


class Response:
    media_type: str | None = None
    charset = "utf-8"

    def __init__(
        self,
        content: t.Any = None,
        status_code: int = 200,
        headers: "Mapping[str, str] | None" = None,
        media_type: str | None = None,
        background: "BackgroundTask | None" = None,
    ) -> None:
        self.status_code = status_code
        if media_type is not None:
            self.media_type = media_type
        self.background = background
        self.body = self.render(content)
        self._init_headers(headers)

    def render(self, content: t.Any) -> bytes:
        if content is None:
            return b""
        if isinstance(content, bytes | memoryview):
            return content
        return content.encode(self.charset)

    def _init_headers(self, headers: "Mapping[str, str] | None" = None) -> None:
        if headers is None:
            raw_headers: list[tuple[bytes, bytes]] = []
            populate_content_length = True
            populate_content_type = True
        else:
            raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
            keys = [h[0] for h in raw_headers]
            populate_content_length = b"content-length" not in keys
            populate_content_type = b"content-type" not in keys

        body = getattr(self, "body", None)
        if (
            body is not None
            and populate_content_length
            and not (self.status_code < 200 or self.status_code in (204, 304))
        ):
            raw_headers.append((b"content-length", str(len(body)).encode("latin-1")))

        content_type = self.media_type
        if content_type is not None and populate_content_type:
            if content_type.startswith("text/") and "charset=" not in content_type.lower():
                content_type += "; charset=" + self.charset
            raw_headers.append((b"content-type", content_type.encode("latin-1")))

        self.raw_headers = raw_headers

    @property
    def headers(self) -> MutableHeaders:
        if not hasattr(self, "_headers"):
            self._headers = MutableHeaders(raw=self.raw_headers)
        return self._headers

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: int | None = None,
        expires: datetime | str | int | None = None,
        path: str | None = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: t.Literal["lax", "strict", "none"] | None = "lax",
        partitioned: bool = False,
    ) -> None:
        cookie: http.cookies.BaseCookie[str] = http.cookies.SimpleCookie()
        cookie[key] = value
        if max_age is not None:
            cookie[key]["max-age"] = max_age
        if expires is not None:
            cookie[key]["expires"] = (
                expires.strftime("%a, %d %b %Y %H:%M:%S GMT") if isinstance(expires, datetime) else expires
            )
        if path is not None:
            cookie[key]["path"] = path
        if domain is not None:
            cookie[key]["domain"] = domain
        if secure:
            cookie[key]["secure"] = True
        if httponly:
            cookie[key]["httponly"] = True
        if samesite is not None:
            assert samesite.lower() in ("strict", "lax", "none"), "samesite must be either 'strict', 'lax' or 'none'"
            cookie[key]["samesite"] = samesite
        if partitioned:
            if sys.version_info < (3, 14):  # pragma: no cover  # PORT: Replace compat when stop supporting 3.13
                raise ValueError("Partitioned cookies are only supported in Python 3.14 and above.")
            cookie[key]["partitioned"] = True

        cookie_val = cookie.output(header="").strip()
        self.raw_headers.append((b"set-cookie", cookie_val.encode("latin-1")))

    def delete_cookie(
        self,
        key: str,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: t.Literal["lax", "strict", "none"] | None = "lax",
    ) -> None:
        self.set_cookie(
            key, max_age=0, expires=0, path=path, domain=domain, secure=secure, httponly=httponly, samesite=samesite
        )

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        prefix = "websocket." if scope.get("type") == "websocket" else ""
        await send(
            types.Message(
                {
                    "type": prefix + "http.response.start",
                    "status": self.status_code,
                    "headers": self.raw_headers,
                }
            )
        )
        await send(types.Message({"type": prefix + "http.response.body", "body": self.body}))

        if self.background is not None:
            await self.background()

    def __hash__(self) -> int:
        return hash(
            (
                self.status_code,
                getattr(self, "media_type"),
                self.background,
                self.body,
                tuple(sorted(self.headers.items())),
            )
        )

    def __eq__(self, value: object, /) -> bool:
        return (
            isinstance(value, Response)
            and self.status_code == value.status_code
            and getattr(self, "media_type") == getattr(value, "media_type")
            and self.background == value.background
            and self.body == value.body
            and self.headers == value.headers
        )
