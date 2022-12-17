import typesystem

__all__ = [
    "APIError",
    "DropCollection",
    "LimitOffsetMeta",
    "LimitOffset",
    "PageNumberMeta",
    "PageNumber",
    "MLModelInput",
    "MLModelOutput",
    "SCHEMAS",
]

SCHEMAS = typesystem.Definitions()

APIError = typesystem.Schema(
    title="APIError",
    fields={
        "status_code": typesystem.fields.Integer(title="status_code", description="HTTP status code"),
        "detail": typesystem.fields.Union(
            any_of=[typesystem.fields.Object(), typesystem.fields.String()], title="detail", description="Error detail"
        ),
        "error": typesystem.fields.String(title="type", description="Exception or error type", allow_null=True),
    },
)
SCHEMAS["APIError"] = APIError

DropCollection = typesystem.Schema(
    title="DropCollection",
    fields={
        "deleted": typesystem.fields.Integer(title="deleted", description="Number of deleted elements"),
    },
)
SCHEMAS["DropCollection"] = DropCollection

LimitOffsetMeta = typesystem.Schema(
    title="LimitOffsetMeta",
    fields={
        "limit": typesystem.fields.Integer(title="limit", description="Number of retrieved items"),
        "offset": typesystem.fields.Integer(title="offset", description="Collection offset"),
        "count": typesystem.fields.Integer(title="count", description="Total number of items", allow_null=True),
    },
)
SCHEMAS["LimitOffsetMeta"] = LimitOffsetMeta

LimitOffset = typesystem.Schema(
    title="LimitOffset",
    fields={
        "meta": typesystem.Reference(
            to="LimitOffsetMeta", definitions=SCHEMAS, title="meta", description="Pagination metadata"
        ),
        "data": typesystem.fields.Array(title="data", description="Paginated data"),
    },
)
SCHEMAS["LimitOffset"] = LimitOffset

PageNumberMeta = typesystem.Schema(
    title="PageNumberMeta",
    fields={
        "page": typesystem.fields.Integer(title="page", description="Current page number"),
        "page_size": typesystem.fields.Integer(title="page_size", description="Page size"),
        "count": typesystem.fields.Integer(title="count", description="Total number of items", allow_null=True),
    },
)
SCHEMAS["PageNumberMeta"] = PageNumberMeta

PageNumber = typesystem.Schema(
    title="PageNumber",
    fields={
        "meta": typesystem.Reference(
            to="PageNumberMeta", definitions=SCHEMAS, title="meta", description="Pagination metadata"
        ),
        "data": typesystem.fields.Array(title="data", description="Paginated data"),
    },
)
SCHEMAS["PageNumber"] = PageNumber

MLModelInput = typesystem.Schema(
    title="MLModelInput",
    fields={
        "input": typesystem.fields.Array(title="input", description="Model input"),
    },
)
SCHEMAS["MLModelInput"] = MLModelInput

MLModelOutput = typesystem.Schema(
    title="MLModelOutput",
    fields={
        "output": typesystem.fields.Array(title="output", description="Model output"),
    },
)
SCHEMAS["MLModelOutput"] = MLModelOutput
