import typing

import marshmallow
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
    UJSONResponse,
)

from flama.exceptions import HTTPException, SerializationError

__all__ = [
    "Response",
    "HTMLResponse",
    "PlainTextResponse",
    "JSONResponse",
    "UJSONResponse",
    "RedirectResponse",
    "StreamingResponse",
    "FileResponse",
    "APIResponse",
    "APIErrorResponse",
    "HTMLFileResponse",
]


class APIError(marshmallow.Schema):
    status_code = marshmallow.fields.Integer(title="status_code", description="HTTP status code", required=True)
    detail = marshmallow.fields.Raw(title="detail", description="Error detail", required=True)
    error = marshmallow.fields.String(title="type", description="Exception or error type")


class APIResponse(JSONResponse):
    media_type = "application/json"

    def __init__(self, schema: typing.Optional[marshmallow.Schema] = None, *args, **kwargs):
        self.schema = schema
        super().__init__(*args, **kwargs)

    def render(self, content: typing.Any):
        # Use output schema to validate and format data
        try:
            if self.schema is not None:
                content = self.schema.dump(content)
        except Exception:
            raise SerializationError(status_code=500)

        if not content:
            return b""

        return super().render(content)


class APIErrorResponse(APIResponse):
    def __init__(
        self, detail: typing.Any, status_code: int = 400, exception: typing.Optional[Exception] = None, *args, **kwargs
    ):
        content = {
            "detail": detail,
            "error": str(exception.__class__.__name__) if exception is not None else None,
            "status_code": status_code,
        }

        super().__init__(schema=APIError(), content=content, status_code=status_code, *args, **kwargs)

        self.detail = detail
        self.exception = exception


class HTMLFileResponse(HTMLResponse):
    def __init__(self, path: str, *args, **kwargs):
        try:
            with open(path) as f:
                content = f.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        super().__init__(content=content, *args, **kwargs)
