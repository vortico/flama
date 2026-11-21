import typing as t

import marshmallow

__all__ = ["ErrorDetail", "APIError", "DropCollection"]

SCHEMAS: dict[str, t.Any] = {}


class ErrorDetail(marshmallow.Schema):
    detail = marshmallow.fields.String(
        metadata={"title": "detail", "description": "Human-readable explanation of the error"}, required=True
    )
    pointer = marshmallow.fields.String(
        metadata={"title": "pointer", "description": "JSON Pointer to the value in error, as a URI fragment"},
        required=True,
    )


SCHEMAS["flama.core.ErrorDetail"] = ErrorDetail


class APIError(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.INCLUDE

    type = marshmallow.fields.String(
        metadata={"title": "type", "description": "URI reference identifying the problem type"},
        load_default="about:blank",
        dump_default="about:blank",
    )
    title = marshmallow.fields.String(
        metadata={"title": "title", "description": "Short summary of the problem type"}, required=True
    )
    status = marshmallow.fields.Integer(metadata={"title": "status", "description": "HTTP status code"}, required=True)
    detail = marshmallow.fields.String(
        metadata={"title": "detail", "description": "Human-readable explanation of this occurrence"}, required=True
    )
    instance = marshmallow.fields.String(
        metadata={"title": "instance", "description": "URI reference identifying this occurrence"}, allow_none=True
    )
    errors = marshmallow.fields.List(
        marshmallow.fields.Nested(ErrorDetail),
        metadata={"title": "errors", "description": "Errors in the request or response"},
        allow_none=True,
    )


SCHEMAS["flama.core.APIError"] = APIError


class DropCollection(marshmallow.Schema):
    deleted = marshmallow.fields.Integer(
        metadata={"title": "deleted", "description": "Number of deleted elements"}, required=True
    )


SCHEMAS["flama.core.DropCollection"] = DropCollection
