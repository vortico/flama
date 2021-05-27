import marshmallow


class APIError(marshmallow.Schema):
    status_code = marshmallow.fields.Integer(title="status_code", description="HTTP status code", required=True)
    detail = marshmallow.fields.Raw(title="detail", description="Error detail", required=True)
    error = marshmallow.fields.String(title="type", description="Exception or error type")


class DropCollection(marshmallow.Schema):
    deleted = marshmallow.fields.Integer(title="deleted", description="Number of deleted elements", required=True)


class LimitOffsetMeta(marshmallow.Schema):
    limit = marshmallow.fields.Integer(title="limit", description="Number of retrieved items")
    offset = marshmallow.fields.Integer(title="offset", description="Collection offset")
    count = marshmallow.fields.Integer(title="count", description="Total number of items", allow_none=True)


class LimitOffsetSchema(marshmallow.Schema):
    meta = marshmallow.fields.Nested(LimitOffsetMeta)
    data = marshmallow.fields.List(marshmallow.fields.Dict())


class PageNumberMeta(marshmallow.Schema):
    page = marshmallow.fields.Integer(title="page", description="Current page number")
    page_size = marshmallow.fields.Integer(title="page_size", description="Page size")
    count = marshmallow.fields.Integer(title="count", description="Total number of items", allow_none=True)


class PageNumberSchema(marshmallow.Schema):
    meta = marshmallow.fields.Nested(PageNumberMeta)
    data = marshmallow.fields.List(marshmallow.fields.Dict())
