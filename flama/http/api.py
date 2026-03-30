import typing as t

from flama import exceptions, schemas, types
from flama.http.response import JSONResponse
from flama.schemas.data_structures import Schema

__all__ = ["APIResponse", "APIErrorResponse"]


class APIResponse(JSONResponse):
    media_type = "application/json"

    def __init__(self, content: t.Any = None, schema: t.Any = None, *args, **kwargs):
        self.schema = schema
        super().__init__(content, *args, **kwargs)

    def render(self, content: t.Any):
        if self.schema is not None:
            try:
                content = Schema.from_type(self.schema).dump(content)
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
        exception: Exception | None = None,
        headers: dict[str, str] | None = None,
        *args,
        **kwargs,
    ):
        content = {
            "detail": detail,
            "error": (str(exception.__class__.__name__) if exception is not None else None),
            "status_code": status_code,
            "headers": headers,
        }

        super().__init__(
            content,
            t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.APIError)],
            *args,
            status_code=status_code,
            **kwargs,
        )

        self.detail = detail
        self.exception = exception
