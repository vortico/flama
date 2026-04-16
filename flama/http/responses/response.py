import abc
import http
import os
import typing as t
from datetime import datetime

from flama import concurrency, exceptions, types
from flama._core.cookies import build_cookie_header
from flama.http.data_structures import MutableHeaders

if t.TYPE_CHECKING:
    from collections.abc import Mapping

    from flama.background import BackgroundTask

__all__ = ["Response", "BufferedResponse", "StreamingResponse"]


class Response(abc.ABC):
    media_type: str | None = None
    charset = "utf-8"

    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: "Mapping[str, str] | None" = None,
        media_type: str | None = None,
        background: "BackgroundTask | None" = None,
    ) -> None:
        self.status_code = status_code
        if media_type is not None:
            self.media_type = media_type
        self.background = background
        self._init_headers(headers)

    def _init_headers(self, headers: "Mapping[str, str] | None" = None) -> None:
        self.raw_headers: list[tuple[bytes, bytes]] = [
            (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()
        ]

        if (content_type := self.media_type) is not None and not any(
            k for (k, _) in self.raw_headers if k == b"content-type"
        ):
            if content_type.startswith("text/") and "charset=" not in content_type.lower():
                content_type += "; charset=" + self.charset
            self.raw_headers.append((b"content-type", content_type.encode("latin-1")))

        self.raw_headers = sorted(self.raw_headers, key=lambda x: x[0])

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
        self.raw_headers.append(
            (
                b"set-cookie",
                build_cookie_header(
                    key,
                    value,
                    max_age=max_age,
                    expires=(
                        None
                        if expires is None
                        else int(expires.timestamp() if isinstance(expires, datetime) else expires)
                    ),
                    path=path,
                    domain=domain,
                    secure=secure,
                    httponly=httponly,
                    samesite=samesite,
                    partitioned=partitioned,
                ).encode("latin-1"),
            )
        )

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

    def __hash__(self) -> int:
        return hash((self.status_code, self.media_type, self.background, tuple(sorted(self.headers.items()))))

    def __eq__(self, value: object, /) -> bool:
        return type(self) is type(value) and hash(self) == hash(value)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        try:
            await self._send_response(scope, receive, send)
        except OSError:
            return

        if self.background is not None:
            await self.background()

    @abc.abstractmethod
    async def _send_response(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None: ...


Content = t.TypeVar("Content")


class BufferedResponse(Response, t.Generic[Content]):
    def __init__(
        self,
        content: Content | None = None,
        /,
        *,
        status_code: int = 200,
        headers: "Mapping[str, str] | None" = None,
        media_type: str | None = None,
        background: "BackgroundTask | None" = None,
        path: str | os.PathLike | None = None,
    ) -> None:
        if path is not None:
            try:
                with open(path) as f:
                    self.body = self.render(f.read())
            except Exception as e:
                raise exceptions.HTTPException(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
        elif content is not None:
            self.body = self.render(content)
        else:
            raise ValueError("Either 'content' or 'path' must be provided")
        super().__init__(status_code=status_code, headers=headers, media_type=media_type, background=background)

    def _init_headers(self, headers: "Mapping[str, str] | None" = None) -> None:
        super()._init_headers(headers)

        if (
            (body := getattr(self, "body", None)) is not None
            and not any(k for (k, _) in self.raw_headers if k == b"content-length")
            and not (self.status_code < 200 or self.status_code in (204, 304))
        ):
            self.raw_headers.append((b"content-length", str(len(body)).encode("latin-1")))

        self.raw_headers = sorted(self.raw_headers, key=lambda x: x[0])

    async def _send_response(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await send(
            types.Message({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
        )
        await send(types.Message({"type": "http.response.body", "body": self.body}))

    def __hash__(self) -> int:
        return hash(
            (self.status_code, self.media_type, self.background, tuple(sorted(self.headers.items())), self.body)
        )

    @abc.abstractmethod
    def render(self, content: Content) -> bytes: ...


class StreamingResponse(Response, t.Generic[Content]):
    def __init__(
        self,
        content: t.Iterable[Content] | t.AsyncIterable[Content],
        /,
        *,
        status_code: int = 200,
        headers: "Mapping[str, str] | None" = None,
        media_type: str | None = None,
        background: "BackgroundTask | None" = None,
    ) -> None:
        self.content = content

        super().__init__(status_code=status_code, headers=headers, media_type=media_type, background=background)

    def _init_headers(self, headers: "Mapping[str, str] | None" = None) -> None:
        super()._init_headers(headers)

        self.raw_headers = sorted([(k, v) for k, v in self.raw_headers if k != b"content-length"], key=lambda x: x[0])

    async def _send_response(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await send(
            types.Message({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
        )

        async for chunk in concurrency.iterate(self.content):
            encoded = self.encode(chunk)
            await send(types.Message({"type": "http.response.body", "body": encoded, "more_body": True}))

        await send(types.Message({"type": "http.response.body", "body": b"", "more_body": False}))

    def __hash__(self) -> int:
        return hash(
            (self.status_code, self.media_type, self.background, tuple(sorted(self.headers.items())), id(self.content))
        )

    @abc.abstractmethod
    def encode(self, chunk: Content) -> bytes: ...
