import typing as t

import marshmallow

__all__ = ["APIError", "DropCollection"]

SCHEMAS: dict[str, t.Any] = {}


class APIError(marshmallow.Schema):
    status_code = marshmallow.fields.Integer(
        metadata={"title": "status_code", "description": "HTTP status code"}, required=True
    )
    detail = marshmallow.fields.Raw(metadata={"title": "detail", "description": "Error detail"}, required=True)
    error = marshmallow.fields.String(metadata={"title": "type", "description": "Exception or error type"})


SCHEMAS["flama.core.APIError"] = APIError


class DropCollection(marshmallow.Schema):
    deleted = marshmallow.fields.Integer(
        metadata={"title": "deleted", "description": "Number of deleted elements"}, required=True
    )


SCHEMAS["flama.core.DropCollection"] = DropCollection
