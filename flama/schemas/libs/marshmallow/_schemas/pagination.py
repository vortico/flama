import marshmallow

__all__ = ["LimitOffset", "LimitOffsetMeta", "PageNumber", "PageNumberMeta"]


class LimitOffsetMeta(marshmallow.Schema):
    limit = marshmallow.fields.Integer(metadata={"title": "limit", "description": "Number of retrieved items"})
    offset = marshmallow.fields.Integer(metadata={"title": "offset", "description": "Collection offset"})
    count = marshmallow.fields.Integer(
        metadata={"title": "count", "description": "Total number of items"}, allow_none=True
    )


class LimitOffset(marshmallow.Schema):
    meta = marshmallow.fields.Nested(
        LimitOffsetMeta(), required=True, metadata={"title": "meta", "description": "Pagination metadata"}
    )
    data = marshmallow.fields.List(
        marshmallow.fields.Dict(), required=True, metadata={"title": "data", "description": "Paginated data"}
    )


class PageNumberMeta(marshmallow.Schema):
    page = marshmallow.fields.Integer(metadata={"title": "page", "description": "Current page number"})
    page_size = marshmallow.fields.Integer(metadata={"title": "page_size", "description": "Page size"})
    count = marshmallow.fields.Integer(
        metadata={"title": "count", "description": "Total number of items"}, allow_none=True
    )


class PageNumber(marshmallow.Schema):
    meta = marshmallow.fields.Nested(
        PageNumberMeta(), required=True, metadata={"title": "meta", "description": "Pagination metadata"}
    )
    data = marshmallow.fields.List(
        marshmallow.fields.Dict(), required=True, metadata={"title": "data", "description": "Paginated data"}
    )
