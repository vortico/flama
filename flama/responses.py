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
)

from flama.types.data_structures import APIError

__all__ = [
    "APIResponse",
    "APIErrorResponse",
    "Response",
    "RedirectResponse",
    "FileResponse",
    "HTMLResponse",
    "JSONResponse",
    "PlainTextResponse",
    "StreamingResponse",
]


class APIResponse(JSONResponse):
    media_type = "application/json"

    def __init__(self, schema: typing.Optional[marshmallow.Schema] = None, *args, **kwargs):
        self.schema = schema
        super().__init__(*args, **kwargs)

    def render(self, content: typing.Any):
        # Use output schema to validate and format data
        if self.schema is not None:
            content = self.schema.dump(content)

        return super().render(content)


class APIErrorResponse(APIResponse):
    def __init__(
        self, detail: typing.Any, status_code: int = 400, exception: typing.Optional[Exception] = None, *args, **kwargs
    ):
        content = {
            "status_code": status_code,
            "detail": detail,
            "error": str(exception.__class__.__name__) if exception is not None else None,
        }

        super().__init__(schema=APIError(), content=content, status_code=status_code, *args, **kwargs)

        self.detail = detail
        self.exception = exception
