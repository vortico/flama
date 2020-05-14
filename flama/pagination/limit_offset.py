import asyncio
import functools
import typing

import marshmallow

from flama.responses import APIResponse
from flama.validation import get_output_schema

try:
    import forge
except Exception:  # pragma: no cover
    forge = None  # type: ignore

__all__ = ["LimitOffsetSchema", "LimitOffsetResponse", "limit_offset"]


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


def limit_offset(func):
    """
    Decorator for adding pagination behavior to a view. That decorator produces a view based on limit-offset and
    it adds three query parameters to control the pagination: limit, offset and count. Offset has a default value of
    zero to start with the first element of the collection, limit default value is defined in
    :class:`LimitOffsetResponse` and count defines if the response will
    define the total number of elements.

    The output schema is also modified by :class:`LimitOffsetSchema`,
    creating a new schema based on it but using the old output schema as the content of its data field.

    :param func: View to be decorated.
    :return: Decorated view.
    """
    assert forge is not None, "`python-forge` must be installed to use Paginator."

    resource_schema = get_output_schema(func)
    data_schema = marshmallow.fields.Nested(resource_schema, many=True) if resource_schema else marshmallow.fields.Raw()

    schema = type(
        "LimitOffsetPaginated" + resource_schema.__class__.__name__,  # Add a prefix to avoid collision
        (LimitOffsetSchema,),
        {"data": data_schema},  # Replace generic with resource schema
    )()

    forge_revision_list = (
        forge.copy(func),
        forge.insert(forge.arg("limit", default=None, type=int), index=-1),
        forge.insert(forge.arg("offset", default=None, type=int), index=-1),
        forge.insert(forge.arg("count", default=True, type=bool), index=-1),
        forge.delete("kwargs"),
        forge.returns(schema),
    )

    try:
        if asyncio.iscoroutinefunction(func):

            @forge.compose(*forge_revision_list)
            @functools.wraps(func)
            async def decorator(*args, limit: int = None, offset: int = None, count: bool = True, **kwargs):
                return LimitOffsetResponse(
                    schema=schema, limit=limit, offset=offset, count=count, content=await func(*args, **kwargs)
                )

        else:

            @forge.compose(*forge_revision_list)
            @functools.wraps(func)
            def decorator(*args, limit: int = None, offset: int = None, count: bool = True, **kwargs):
                return LimitOffsetResponse(
                    schema=schema, limit=limit, offset=offset, count=count, content=func(*args, **kwargs)
                )

    except ValueError as e:
        raise TypeError("Paginated views must define **kwargs param") from e

    return decorator
