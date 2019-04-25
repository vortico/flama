import typing

import marshmallow

from flama.responses import APIResponse

__all__ = ["LimitOffsetSchema", "LimitOffsetResponse"]


class LimitOffsetMeta(marshmallow.Schema):
    limit = marshmallow.fields.Integer(title="limit", description="Number of retrieved items")
    offset = marshmallow.fields.Integer(title="offset", description="Collection offset")
    count = marshmallow.fields.Integer(title="count", description="Total number of items", allow_none=True)


class LimitOffsetSchema(marshmallow.Schema):
    meta = marshmallow.fields.Nested(LimitOffsetMeta)
    data = marshmallow.fields.List(marshmallow.fields.Dict())


class LimitOffsetResponse(APIResponse):
    """
    Response paginated based on a limit of elements and an offset.

    First 10 elements:
        /resource?offset=0&limit=10
    Elements 20-30:
        /resource?offset=20&limit=10
    """

    default_limit = 10

    def __init__(
        self,
        schema: marshmallow.Schema,
        offset: typing.Optional[typing.Union[int, str]] = None,
        limit: typing.Optional[typing.Union[int, str]] = None,
        count: typing.Optional[bool] = True,
        **kwargs
    ):
        self.offset = int(offset) if offset is not None else 0
        self.limit = int(limit) if limit is not None else self.default_limit
        self.count = count
        super().__init__(schema=schema, **kwargs)

    def render(self, content: typing.Sequence):
        init = self.offset
        end = self.offset + self.limit
        return super().render(
            {
                "meta": {"limit": self.limit, "offset": self.offset, "count": len(content) if self.count else None},
                "data": content[init:end],
            }
        )
