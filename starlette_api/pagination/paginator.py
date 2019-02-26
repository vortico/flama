import functools

import forge

from starlette_api.pagination.limit_offset import LimitOffsetResponse
from starlette_api.pagination.page_number import PageNumberResponse
from starlette_api.validation import get_output_schema

__all__ = ["Paginator"]


class Paginator:
    @classmethod
    def page_number(cls, func):
        schema = get_output_schema(func)

        try:

            @forge.compose(
                forge.copy(func),
                forge.delete("kwargs"),
                forge.insert(forge.arg("page", default=None, type=int), index=-1),
                forge.insert(forge.arg("page_size", default=None, type=int), index=-1),
                forge.insert(forge.arg("count", default=True, type=bool), index=-1),
            )
            @functools.wraps(func)
            def decorator(*args, page: int = None, page_size: int = None, count: bool = True, **kwargs):
                content = func(*args, **kwargs)
                return PageNumberResponse(schema=schema, page=page, page_size=page_size, count=count, content=content)

        except ValueError as e:
            raise TypeError("Paginated views must define **kwargs param") from e

        return decorator

    @classmethod
    def limit_offset(cls, func):
        schema = get_output_schema(func)

        try:

            @forge.compose(
                forge.copy(func),
                forge.delete("kwargs"),
                forge.insert(forge.arg("limit", default=None, type=int), index=-1),
                forge.insert(forge.arg("offset", default=None, type=int), index=-1),
                forge.insert(forge.arg("count", default=True, type=bool), index=-1),
            )
            @functools.wraps(func)
            def decorator(*args, limit: int = None, offset: int = None, count: bool = True, **kwargs):
                content = func(*args, **kwargs)
                return LimitOffsetResponse(schema=schema, limit=limit, offset=offset, count=count, content=content)

        except ValueError as e:
            raise TypeError("Paginated views must define **kwargs param") from e

        return decorator
