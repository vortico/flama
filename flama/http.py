import datetime
import enum
import html
import json
import os
import typing as t
import uuid
from pathlib import Path

import jinja2
import starlette.requests
import starlette.responses
import starlette.schemas

from flama import schemas, types
from flama.exceptions import HTTPException, SerializationError

if t.TYPE_CHECKING:
    import flama.schemas.types

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

Method = enum.Enum("Method", ["GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"])
Request = starlette.requests.Request


class Response(starlette.responses.Response):
    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]


class HTMLResponse(starlette.responses.HTMLResponse, Response):
    __call__ = Response.__call__  # type: ignore[assignment]


class PlainTextResponse(starlette.responses.PlainTextResponse, Response):
    __call__ = Response.__call__  # type: ignore[assignment]


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, datetime.timedelta):
            # split seconds to larger units
            seconds = obj.total_seconds()
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
        return super().default(obj)


class JSONResponse(starlette.responses.JSONResponse, Response):
    def render(self, content: t.Any) -> bytes:
        return json.dumps(
            content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":"), cls=EnhancedJSONEncoder
        ).encode("utf-8")


class RedirectResponse(starlette.responses.RedirectResponse, Response):
    __call__ = Response.__call__  # type: ignore[assignment]


class StreamingResponse(starlette.responses.StreamingResponse, Response):
    __call__ = Response.__call__  # type: ignore[assignment]


class FileResponse(starlette.responses.FileResponse, Response):
    __call__ = Response.__call__  # type: ignore[assignment]


class APIResponse(JSONResponse):
    media_type = "application/json"

    def __init__(self, content: t.Any = None, schema: t.Optional["flama.schemas.types.Schema"] = None, *args, **kwargs):
        self.schema = schema
        super().__init__(content, *args, **kwargs)

    def render(self, content: t.Any):
        if self.schema is not None:
            try:
                content = schemas.Schema(self.schema).dump(content)
            except schemas.SchemaValidationError as e:
                raise SerializationError(status_code=500, detail=e.errors)

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

        super().__init__(content, schemas.schemas.APIError, status_code=status_code, *args, **kwargs)

        self.detail = detail
        self.exception = exception


class HTMLFileResponse(HTMLResponse):
    def __init__(self, path: str, *args, **kwargs):
        try:
            with open(path) as f:
                content = f.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

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

    def _escape(self, value: types.JSON) -> types.JSON:
        if isinstance(value, (list, tuple)):
            return [self._escape(x) for x in value]

        if isinstance(value, dict):
            return {k: self._escape(v) for k, v in value.items()}

        if isinstance(value, str):
            return html.escape(value).replace("\n", "&#13;")

        return value

    def safe_json(self, value: types.JSON):
        return json.dumps(self._escape(value)).replace('"', '\\"')


class _ReactTemplateResponse(HTMLTemplateResponse):
    templates = _ReactTemplatesEnvironment(
        loader=jinja2.ChoiceLoader(
            [jinja2.FileSystemLoader(Path(os.curdir) / "templates"), jinja2.PackageLoader("flama", "templates")]
        )
    )


class OpenAPIResponse(Response, starlette.schemas.OpenAPIResponse):
    def render(self, content: t.Any) -> bytes:
        assert isinstance(content, dict), "The schema passed to OpenAPIResponse should be a dictionary."

        return json.dumps(content).encode("utf-8")
