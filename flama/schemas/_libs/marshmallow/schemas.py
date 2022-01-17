import marshmallow

__all__ = [
    "APIError",
    "DropCollection",
    "LimitOffsetMeta",
    "LimitOffset",
    "PageNumberMeta",
    "PageNumber",
    "SCHEMAS",
]


class APIError(marshmallow.Schema):
    status_code = marshmallow.fields.Integer(
        metadata={"title": "status_code", "description": "HTTP status code"}, required=True
    )
    detail = marshmallow.fields.Raw(metadata={"title": "detail", "description": "Error detail"}, required=True)
    error = marshmallow.fields.String(metadata={"title": "type", "description": "Exception or error type"})


class DropCollection(marshmallow.Schema):
    deleted = marshmallow.fields.Integer(
        metadata={"title": "deleted", "description": "Number of deleted elements"}, required=True
    )


class LimitOffsetMeta(marshmallow.Schema):
    limit = marshmallow.fields.Integer(metadata={"title": "limit", "description": "Number of retrieved items"})
    offset = marshmallow.fields.Integer(metadata={"title": "offset", "description": "Collection offset"})
    count = marshmallow.fields.Integer(
        metadata={"title": "count", "description": "Total number of items"}, allow_none=True
    )


class LimitOffset(marshmallow.Schema):
    meta = marshmallow.fields.Nested(LimitOffsetMeta, required=True)
    data = marshmallow.fields.List(marshmallow.fields.Dict(), required=True)


class PageNumberMeta(marshmallow.Schema):
    page = marshmallow.fields.Integer(metadata={"title": "page", "description": "Current page number"})
    page_size = marshmallow.fields.Integer(metadata={"title": "page_size", "description": "Page size"})
    count = marshmallow.fields.Integer(
        metadata={"title": "count", "description": "Total number of items"}, allow_none=True
    )


class PageNumber(marshmallow.Schema):
    meta = marshmallow.fields.Nested(PageNumberMeta, required=True)
    data = marshmallow.fields.List(marshmallow.fields.Dict(), required=True)


SCHEMAS = {
    "APIError": APIError,
    "DropCollection": DropCollection,
    "LimitOffsetMeta": LimitOffsetMeta,
    "LimitOffset": LimitOffset,
    "PageNumberMeta": PageNumberMeta,
    "PageNumber": PageNumber,
}
