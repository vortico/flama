import datetime
import html
import json
import os
import typing
from pathlib import Path

import jinja2
from starlette import schemas as starlette_schemas
from starlette.responses import FileResponse, HTMLResponse
from starlette.responses import JSONResponse as StarletteJSONResponse
from starlette.responses import PlainTextResponse, RedirectResponse, Response, StreamingResponse

from flama import schemas
from flama.exceptions import HTTPException, SerializationError
from flama.schemas.types import Schema

__all__ = [
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

from flama.types import JSON


assert (
    Path(__file__).parent / "templates"
).exists(), "'flama/templates' was not found. Please run 'make install' to ensure correct installation."


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        elif isinstance(obj, datetime.timedelta):
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


class JSONResponse(StarletteJSONResponse):
    def render(self, content: typing.Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=EnhancedJSONEncoder,
        ).encode("utf-8")


class APIResponse(JSONResponse):
    media_type = "application/json"

    def __init__(self, content: typing.Any = None, schema: typing.Optional[Schema] = None, *args, **kwargs):
        self.schema = schema
        super().__init__(content, *args, **kwargs)

    def render(self, content: typing.Any):
        if self.schema is not None:
            try:
                content = schemas.adapter.dump(self.schema, content)
                schemas.adapter.validate(self.schema, content)
            except schemas.SchemaValidationError as e:
                raise SerializationError(status_code=500, detail=e.errors)

        if not content:
            return b""

        return super().render(content)


class APIErrorResponse(APIResponse):
    def __init__(
        self,
        detail: typing.Any,
        status_code: int = 400,
        exception: typing.Optional[Exception] = None,
        headers: typing.Optional[typing.Dict[str, str]] = None,
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


class _TemplatesEnvironment(jinja2.Environment):
    def __init__(self, *args, **kwargs):
        super().__init__(
            loader=jinja2.ChoiceLoader(
                [jinja2.FileSystemLoader(Path(os.curdir) / "templates"), jinja2.PackageLoader("flama", "templates")]
            ),
            block_start_string="||%",
            block_end_string="%||",
            variable_start_string="||@",
            variable_end_string="@||",
            *args,
            **kwargs,
        )

        self.filters["safe_json"] = self.safe_json

    def _escape(self, value: JSON) -> JSON:
        if isinstance(value, (list, tuple)):
            return [self._escape(x) for x in value]

        if isinstance(value, dict):
            return {k: self._escape(v) for k, v in value.items()}

        if isinstance(value, str):
            return html.escape(value).replace("\n", "&#13;")

        return value

    def safe_json(self, value: JSON):
        return json.dumps(self._escape(value)).replace('"', '\\"')


class HTMLTemplateResponse(HTMLResponse):
    templates = _TemplatesEnvironment()

    def __init__(self, template: str, context: typing.Dict[str, typing.Any] = None, *args, **kwargs):
        if context is None:
            context = {}

        super().__init__(self.templates.get_template(template).render(**context), *args, **kwargs)


class OpenAPIResponse(starlette_schemas.OpenAPIResponse):
    def render(self, content: typing.Any) -> bytes:
        assert isinstance(content, dict), "The schema passed to OpenAPIResponse should be a dictionary."

        return json.dumps(content).encode("utf-8")
