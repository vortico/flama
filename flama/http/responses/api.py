import dataclasses
import http as stdlib_http
import os
import typing as t

from flama import schemas, types
from flama.http.exceptions import HTTPException, SerializationError
from flama.http.responses.json import JSONResponse
from flama.schemas.libs._libraries import libraries
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
                raise SerializationError(errors=e.errors)

        return super().render(content)


class APIErrorResponse(APIResponse):
    """Error response carrying a problem detail (RFC 9457), served as ``application/problem+json``.

    :param detail: Human-readable explanation of this occurrence, the status phrase by default.
    :param status_code: HTTP status code.
    :param type: URI reference identifying the problem type, ``about:blank`` when the status says everything.
    :param title: Short summary of the problem type, the status phrase by default.
    :param instance: URI reference identifying this occurrence, such as the path requested.
    :param errors: Errors located by a JSON Pointer into the value they were raised for.
    :param extensions: Extension members of the problem.
    :param headers: Headers of the response.
    :raises ValueError: If an extension member is named after a member of the problem.
    """

    media_type = "application/problem+json"

    def __init__(
        self,
        detail: str | None = None,
        status_code: int = 400,
        *,
        type: str = "about:blank",
        title: str | None = None,
        instance: str | None = None,
        errors: "t.Sequence[types.ErrorDetail]" = (),
        extensions: "Mapping[str, t.Any] | None" = None,
        headers: "Mapping[str, str] | None" = None,
        background: "BackgroundTask | None" = None,
    ) -> None:
        if reserved := HTTPException.MEMBERS & set(extensions or {}):
            raise ValueError(f"Extension members cannot be named after members of the problem: {sorted(reserved)}")

        phrase = stdlib_http.HTTPStatus(status_code).phrase
        super().__init__(
            {
                "type": type,
                "title": title if title is not None else phrase,
                "status": status_code,
                "detail": detail if detail is not None else phrase,
                **({"instance": instance} if instance is not None else {}),
                **({"errors": [dataclasses.asdict(x) for x in errors]} if errors else {}),
                **(extensions or {}),
            },
            schema=libraries.default.schemas.core.APIError,
            status_code=status_code,
            headers=headers,
            background=background,
        )

    def render(self, content: t.Any) -> bytes:
        # The problem is built here, and its schema would drop the extension members it does not declare.
        return JSONResponse.render(self, content)
