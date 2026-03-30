import dataclasses
import datetime
import enum
import inspect
import json
import os
import pathlib
import typing as t
import uuid

import starlette.responses

from flama.types.asgi import Receive, Scope, Send
from flama.url import URL, Path

__all__ = [
    "Response",
    "HTMLResponse",
    "PlainTextResponse",
    "JSONResponse",
    "RedirectResponse",
    "StreamingResponse",
    "FileResponse",
    "EnhancedJSONEncoder",
]


class Response(starlette.responses.Response):
    async def __call__(  # ty: ignore[invalid-method-override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        await super().__call__(scope, receive, send)  # ty: ignore[invalid-argument-type]

    def __hash__(self) -> int:
        return hash(
            (
                self.status_code,
                getattr(self, "media_type"),
                self.background,
                self.body,
                self.headers,
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


class HTMLResponse(starlette.responses.HTMLResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)


class PlainTextResponse(starlette.responses.PlainTextResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, pathlib.Path | os.PathLike | uuid.UUID | Path | URL):
            return str(o)
        if isinstance(o, bytes | bytearray):
            return o.decode("utf-8")
        if isinstance(o, enum.Enum):
            return o.value
        if isinstance(o, set | frozenset):
            return list(o)
        if isinstance(o, datetime.datetime | datetime.date | datetime.time):
            return o.isoformat()
        if isinstance(o, datetime.timedelta):
            seconds = o.total_seconds()
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)
            days, hours, minutes = map(int, (days, hours, minutes))
            seconds = round(seconds, 6)

            formatted_units = (
                (days, f"{days:02d}".lstrip("0") + "D"),
                (hours, f"{hours:02d}".lstrip("0") + "H"),
                (minutes, f"{minutes:02d}".lstrip("0") + "M"),
                (seconds, f"{seconds:.6f}".strip("0") + "S"),
            )

            return "P" + "".join([formatted_value for value, formatted_value in formatted_units if value])
        if inspect.isclass(o) and issubclass(o, BaseException):
            return o.__name__
        if isinstance(o, BaseException):
            return repr(o)
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        return super().default(o)


class JSONResponse(starlette.responses.JSONResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)

    def render(self, content: t.Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=EnhancedJSONEncoder,
        ).encode("utf-8")


class RedirectResponse(starlette.responses.RedirectResponse, Response):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)


class StreamingResponse(starlette.responses.StreamingResponse, Response):
    async def __call__(  # ty: ignore[invalid-method-override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        await super().__call__(scope, receive, send)  # ty: ignore[invalid-argument-type]


class FileResponse(starlette.responses.FileResponse, Response):
    async def __call__(  # ty: ignore[invalid-method-override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        await super().__call__(scope, receive, send)  # ty: ignore[invalid-argument-type]
