import asyncio
import functools

import marshmallow

from flama.pagination.limit_offset import LimitOffsetResponse, LimitOffsetSchema
from flama.pagination.page_number import PageNumberResponse, PageNumberSchema
from flama.validation import get_output_schema

try:
    import forge
except Exception:  # pragma: no cover
    forge = None  # type: ignore

__all__ = ["Paginator"]


class Paginator:
    @classmethod
    def page_number(cls, func):
        """
        Decorator for adding pagination behavior to a view. That decorator produces a view based on page numbering and
        it adds three query parameters to control the pagination: page, page_size and count. Page has a default value of
        first page, page_size default value is defined in
        :class:`PageNumberResponse` and count defines if the response will define
        the total number of elements.

        The output schema is also modified by :class:`PageNumberSchema`, creating
        a new schema based on it but using the old output schema as the content of its data field.

        :param func: View to be decorated.
        :return: Decorated view.
        """
        assert forge is not None, "`python-forge` must be installed to use OpenAPIResponse."

        resource_schema = get_output_schema(func)

        schema = type(
            "PageNumberPaginated" + resource_schema.__class__.__name__,  # Add a prefix to avoid collision
            (PageNumberSchema,),
            {"data": marshmallow.fields.Nested(resource_schema, many=True)},  # Replace generic with resource schema
        )()

        forge_revision_list = (
            forge.copy(func),
            forge.insert(forge.arg("page", default=None, type=int), index=-1),
            forge.insert(forge.arg("page_size", default=None, type=int), index=-1),
            forge.insert(forge.arg("count", default=True, type=bool), index=-1),
            forge.delete("kwargs"),
            forge.returns(schema),
        )

        try:
            if asyncio.iscoroutinefunction(func):

                @forge.compose(*forge_revision_list)
                @functools.wraps(func)
                async def decorator(*args, page: int = None, page_size: int = None, count: bool = True, **kwargs):
                    return PageNumberResponse(
                        schema=schema, page=page, page_size=page_size, count=count, content=await func(*args, **kwargs)
                    )

            else:

                @forge.compose(*forge_revision_list)
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
        assert forge is not None, "`python-forge` must be installed to use OpenAPIResponse."

        resource_schema = get_output_schema(func)

        schema = type(
            "LimitOffsetPaginated" + resource_schema.__class__.__name__,  # Add a prefix to avoid collision
            (LimitOffsetSchema,),
            {"data": marshmallow.fields.Nested(resource_schema, many=True)},  # Replace generic with resource schema
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
