import dataclasses
import datetime
import enum
import html
import inspect
import json
import os
import sys
import typing as t
import uuid
from pathlib import Path

import jinja2
import starlette.requests
import starlette.responses
import starlette.schemas

from flama import exceptions, schemas, types

if sys.version_info < (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover

    class StrEnum(str, enum.Enum):
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

    enum.StrEnum = StrEnum  # type: ignore

__all__ = [
    "Method",
    "Request",
    "Response",
    "HTMLResponse",
    "PlainTextResponse",
    "JSONResponse",
    "RedirectResponse",
    "StreamingResponse",
    "FileResponse",
    "APIResponse",
    "APIErrorResponse",
    "HTMLFileResponse",
    "HTMLTemplateResponse",
    "OpenAPIResponse",
]

Method = enum.StrEnum(  # type: ignore # PORT: Remove this comment when stop supporting 3.10
    "Method", ["GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"]
)
Request = starlette.requests.Request


class Response(starlette.responses.Response):
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]


class HTMLResponse(starlette.responses.HTMLResponse, Response):
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]


class PlainTextResponse(starlette.responses.PlainTextResponse, Response):
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (Path, os.PathLike, uuid.UUID)):
            return str(o)
        if isinstance(o, (bytes, bytearray)):
            return o.decode("utf-8")
        if isinstance(o, enum.Enum):
            return o.value
        if isinstance(o, (set, frozenset)):
            return list(o)
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        if isinstance(o, datetime.timedelta):
            # split seconds to larger units
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
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]

    def render(self, content: t.Any) -> bytes:
        if isinstance(content, types.Schema):
            content = dict(content)

        return json.dumps(
            content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":"), cls=EnhancedJSONEncoder
        ).encode("utf-8")


class RedirectResponse(starlette.responses.RedirectResponse, Response):
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]


class StreamingResponse(starlette.responses.StreamingResponse, Response):
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]


class FileResponse(starlette.responses.FileResponse, Response):
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]


class APIResponse(JSONResponse):
    media_type = "application/json"

    def __init__(self, content: t.Any = None, schema: t.Optional[t.Type["types.Schema"]] = None, *args, **kwargs):
        self.schema = schema
        super().__init__(content, *args, **kwargs)

    def render(self, content: t.Any):
        if self.schema is not None:
            try:
                content = schemas.Schema.from_type(self.schema).dump(content)
            except schemas.SchemaValidationError as e:
                raise exceptions.SerializationError(status_code=500, detail=e.errors)

        if not content:
            return b""

        return super().render(content)


class APIErrorResponse(APIResponse):
    def __init__(
        self,
        detail: t.Any,
        status_code: int = 400,
        exception: t.Optional[Exception] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        *args,
        **kwargs,
    ):
        content = {
            "detail": detail,
            "error": str(exception.__class__.__name__) if exception is not None else None,
            "status_code": status_code,
            "headers": headers,
        }

        super().__init__(
            content, schema=types.Schema[schemas.schemas.APIError], status_code=status_code, *args, **kwargs
        )

        self.detail = detail
        self.exception = exception


class HTMLFileResponse(HTMLResponse):
    def __init__(self, path: str, *args, **kwargs):
        try:
            with open(path) as f:
                content = f.read()
        except Exception as e:
            raise exceptions.HTTPException(status_code=500, detail=str(e))

        super().__init__(content, *args, **kwargs)


class HTMLTemplateResponse(HTMLResponse):
    templates = jinja2.Environment(
        loader=jinja2.ChoiceLoader(
            [jinja2.FileSystemLoader(Path(os.curdir) / "templates"), jinja2.PackageLoader("flama", "templates")]
        )
    )

    def __init__(self, template: str, context: t.Optional[t.Dict[str, t.Any]] = None, *args, **kwargs):
        if context is None:
            context = {}

        super().__init__(self.templates.get_template(template).render(**context), *args, **kwargs)


class _ReactTemplatesEnvironment(jinja2.Environment):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **{
                **kwargs,
                "block_start_string": "||%",
                "block_end_string": "%||",
                "variable_start_string": "||@",
                "variable_end_string": "@||",
            },
        )

        self.filters["safe_json"] = self.safe_json

    def _escape(self, value: types.JSONField) -> types.JSONField:
        if isinstance(value, (list, tuple)):
            return [self._escape(x) for x in value]

        if isinstance(value, dict):
            return {k: self._escape(v) for k, v in value.items()}

        if isinstance(value, str):
            return html.escape(value).replace("\n", "&#13;")

        return value

    def safe_json(self, value: types.JSONField):
        return json.dumps(self._escape(value)).replace('"', '\\"')


class _ReactTemplateResponse(HTMLTemplateResponse):
    templates = _ReactTemplatesEnvironment(
        loader=jinja2.ChoiceLoader(
            [jinja2.FileSystemLoader(Path(os.curdir) / "templates"), jinja2.PackageLoader("flama", "templates")]
        )
    )


class OpenAPIResponse(starlette.schemas.OpenAPIResponse, Response):
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]

    def render(self, content: t.Any) -> bytes:
        assert isinstance(content, dict), "The schema passed to OpenAPIResponse should be a dictionary."

        return json.dumps(content).encode("utf-8")
