import os
import typing as t

from flama import exceptions, schemas, types
from flama.http.responses.json import JSONResponse
from flama.types.schemas import SchemaPayload

if t.TYPE_CHECKING:
    from collections.abc import Mapping

    from flama.background import BackgroundTask

__all__ = ["APIResponse", "APIErrorResponse"]


class APIResponse(JSONResponse[SchemaPayload], types.SchemaResponse[SchemaPayload], t.Generic[SchemaPayload]):
    """JSON response whose body is serialised with a schema.

    The schema given makes the type argument, as in ``APIResponse[Item]``. A response built without a schema
    takes the one in the endpoint's return annotation when returned from it.
    """

    media_type = "application/json"

    def __init__(
        self,
        content: t.Any = None,
        /,
        *,
        schema: type[SchemaPayload] | SchemaPayload | None = None,
        status_code: int = 200,
        headers: "Mapping[str, str] | None" = None,
        media_type: str | None = None,
        background: "BackgroundTask | None" = None,
        path: str | os.PathLike | None = None,
    ) -> None:
        self.schema = schema
        super().__init__(
            content, status_code=status_code, headers=headers, media_type=media_type, background=background, path=path
        )

    def render(self, content: t.Any) -> bytes:
        if self.schema is not None:
            from flama.schemas.data_structures import Schema

            try:
                content = Schema.from_type(self.schema).dump(content)
            except schemas.SchemaValidationError as e:
                raise exceptions.SerializationError(status_code=500, detail=e.errors)

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
        super().__init__(
            {
                "detail": detail,
                "error": (str(exception.__class__.__name__) if exception is not None else None),
                "status_code": status_code,
                "headers": headers,
            },
            *args,
            schema=schemas.schemas.core.APIError,
            status_code=status_code,
            headers=headers,
            **kwargs,
        )

        self.detail = detail
        self.exception = exception
