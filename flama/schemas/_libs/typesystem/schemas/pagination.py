from typesystem import Reference, Schema, fields

from flama.schemas._libs.typesystem.schemas.core import SCHEMAS

__all__ = ["LimitOffset", "LimitOffsetMeta", "PageNumber", "PageNumberMeta"]

LimitOffsetMeta = Schema(
    title="LimitOffsetMeta",
    fields={
        "limit": fields.Integer(title="limit", description="Number of retrieved items"),
        "offset": fields.Integer(title="offset", description="Collection offset"),
        "count": fields.Integer(title="count", description="Total number of items", allow_null=True),
    },
)
SCHEMAS["flama.pagination.LimitOffsetMeta"] = LimitOffsetMeta

LimitOffset = Schema(
    title="LimitOffset",
    fields={
        "meta": Reference(
            to="flama.pagination.LimitOffsetMeta", definitions=SCHEMAS, title="meta", description="Pagination metadata"
        ),
        "data": fields.Array(title="data", description="Paginated data"),
    },
)
SCHEMAS["flama.pagination.LimitOffset"] = LimitOffset

PageNumberMeta = Schema(
    title="PageNumberMeta",
    fields={
        "page": fields.Integer(title="page", description="Current page number"),
        "page_size": fields.Integer(title="page_size", description="Page size"),
        "count": fields.Integer(title="count", description="Total number of items", allow_null=True),
    },
)
SCHEMAS["flama.pagination.PageNumberMeta"] = PageNumberMeta

PageNumber = Schema(
    title="PageNumber",
    fields={
        "meta": Reference(
            to="flama.pagination.PageNumberMeta", definitions=SCHEMAS, title="meta", description="Pagination metadata"
        ),
        "data": fields.Array(title="data", description="Paginated data"),
    },
)
SCHEMAS["flama.pagination.PageNumber"] = PageNumber
