import typesystem

__all__ = [
    "APIError",
    "DropCollection",
    "LimitOffsetMeta",
    "LimitOffset",
    "PageNumberMeta",
    "PageNumber",
    "SCHEMAS",
]

SCHEMAS = {}


APIError = typesystem.Schema(
    fields={
        "status_code": typesystem.fields.Integer(title="status_code", description="HTTP status code"),
        "detail": typesystem.fields.Union(
            any_of=[typesystem.fields.Object(), typesystem.fields.String()], title="detail", description="Error detail"
        ),
        "error": typesystem.fields.String(title="type", description="Exception or error type", allow_null=True),
    }
)
SCHEMAS["APIError"] = APIError


DropCollection = typesystem.Schema(
    fields={
        "deleted": typesystem.fields.Integer(title="deleted", description="Number of deleted elements"),
    }
)
SCHEMAS["DropCollection"] = DropCollection


LimitOffsetMeta = typesystem.Schema(
    fields={
        "limit": typesystem.fields.Integer(title="limit", description="Number of retrieved items"),
        "offset": typesystem.fields.Integer(title="offset", description="Collection offset"),
        "count": typesystem.fields.Integer(title="count", description="Total number of items", allow_null=True),
    }
)
SCHEMAS["LimitOffsetMeta"] = LimitOffsetMeta


LimitOffset = typesystem.Schema(
    fields={
        "meta": typesystem.Reference(to="LimitOffsetMeta", definitions=SCHEMAS),
        "data": typesystem.fields.Array(typesystem.fields.Any()),
    }
)
SCHEMAS["LimitOffset"] = LimitOffset


PageNumberMeta = typesystem.Schema(
    fields={
        "page": typesystem.fields.Integer(title="page", description="Current page number"),
        "page_size": typesystem.fields.Integer(title="page_size", description="Page size"),
        "count": typesystem.fields.Integer(title="count", description="Total number of items", allow_null=True),
    }
)
SCHEMAS["PageNumberMeta"] = PageNumberMeta


PageNumber = typesystem.Schema(
    fields={
        "meta": typesystem.Reference(to="PageNumberMeta", definitions=SCHEMAS),
        "data": typesystem.fields.Array(typesystem.fields.Any()),
    }
)
SCHEMAS["PageNumber"] = PageNumber
