from typesystem import Definitions, Schema, fields

__all__ = ["APIError", "DropCollection"]

SCHEMAS = Definitions()

APIError = Schema(
    title="APIError",
    fields={
        "status_code": fields.Integer(title="status_code", description="HTTP status code"),
        "detail": fields.Union(any_of=[fields.Object(), fields.String()], title="detail", description="Error detail"),
        "error": fields.String(title="type", description="Exception or error type", allow_null=True),
    },
)
SCHEMAS["flama.core.APIError"] = APIError

DropCollection = Schema(
    title="DropCollection",
    fields={
        "deleted": fields.Integer(title="deleted", description="Number of deleted elements"),
    },
)
SCHEMAS["flama.core.DropCollection"] = DropCollection
