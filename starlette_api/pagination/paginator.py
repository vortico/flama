import functools

import forge
import marshmallow

from starlette_api.pagination.limit_offset import LimitOffsetResponse, LimitOffsetSchema
from starlette_api.pagination.page_number import PageNumberResponse, PageNumberSchema
from starlette_api.validation import get_output_schema

__all__ = ["Paginator"]


class Paginator:
    @classmethod
    def page_number(cls, func):
        resource_schema = get_output_schema(func)

        schema = type(
            "PageNumberPaginated" + resource_schema.__class__.__name__,  # Add a prefix to avoid collision
            (PageNumberSchema,),
            {"data": marshmallow.fields.Nested(resource_schema, many=True)},  # Replace generic with resource schema
        )()

        try:

            @forge.compose(
                forge.copy(func),
                forge.delete("kwargs"),
                forge.insert(forge.arg("page", default=None, type=int), index=-1),
                forge.insert(forge.arg("page_size", default=None, type=int), index=-1),
                forge.insert(forge.arg("count", default=True, type=bool), index=-1),
                forge.returns(schema),
            )
            @functools.wraps(func)
            def decorator(*args, page: int = None, page_size: int = None, count: bool = True, **kwargs):
                return PageNumberResponse(
                    schema=schema, page=page, page_size=page_size, count=count, content=func(*args, **kwargs)
                )

        except ValueError as e:
            raise TypeError("Paginated views must define **kwargs param") from e

        return decorator

    @classmethod
    def limit_offset(cls, func):
        resource_schema = get_output_schema(func)

        schema = type(
            "LimitOffsetPaginated" + resource_schema.__class__.__name__,  # Add a prefix to avoid collision
            (LimitOffsetSchema,),
            {"data": marshmallow.fields.Nested(resource_schema, many=True)},  # Replace generic with resource schema
        )()
        try:

            @forge.compose(
                forge.copy(func),
                forge.delete("kwargs"),
                forge.insert(forge.arg("limit", default=None, type=int), index=-1),
                forge.insert(forge.arg("offset", default=None, type=int), index=-1),
                forge.insert(forge.arg("count", default=True, type=bool), index=-1),
                forge.returns(schema),
            )
            @functools.wraps(func)
            def decorator(*args, limit: int = None, offset: int = None, count: bool = True, **kwargs):
                return LimitOffsetResponse(
                    schema=schema, limit=limit, offset=offset, count=count, content=func(*args, **kwargs)
                )

        except ValueError as e:
            raise TypeError("Paginated views must define **kwargs param") from e

        return decorator
