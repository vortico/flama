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

__all__ = ["PageNumberSchema", "PageNumberResponse", "page_number"]


class PageNumberMeta(marshmallow.Schema):
    page = marshmallow.fields.Integer(title="page", description="Current page number")
    page_size = marshmallow.fields.Integer(title="page_size", description="Page size")
    count = marshmallow.fields.Integer(title="count", description="Total number of items", allow_none=True)


class PageNumberSchema(marshmallow.Schema):
    meta = marshmallow.fields.Nested(PageNumberMeta)
    data = marshmallow.fields.List(marshmallow.fields.Dict())


class PageNumberResponse(APIResponse):
    """
    Response paginated based on a page number and a page size.

    First 10 elements:
        /resource?page=1
    Third 10 elements:
        /resource?page=3
    First 20 elements:
        /resource?page=1&page_size=20
    """

    default_page_size = 10

    def __init__(
        self,
        schema: marshmallow.Schema,
        page: typing.Optional[typing.Union[int, str]] = None,
        page_size: typing.Optional[typing.Union[int, str]] = None,
        count: typing.Optional[bool] = True,
        **kwargs
    ):
        self.page_number = int(page) if page is not None else 1
        self.page_size = int(page_size) if page_size is not None else self.default_page_size
        self.count = count
        super().__init__(schema=schema, **kwargs)

    def render(self, content: typing.Sequence):
        init = (self.page_number - 1) * self.page_size
        end = self.page_number * self.page_size

        return super().render(
            {
                "meta": {
                    "page": self.page_number,
                    "page_size": self.page_size,
                    "count": len(content) if self.count else None,
                },
                "data": content[init:end],
            }
        )


def page_number(func):
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
    assert forge is not None, "`python-forge` must be installed to use Paginator."

    resource_schema = get_output_schema(func)
    data_schema = marshmallow.fields.Nested(resource_schema, many=True) if resource_schema else marshmallow.fields.Raw()

    schema = type(
        "PageNumberPaginated" + resource_schema.__class__.__name__,  # Add a prefix to avoid collision
        (PageNumberSchema,),
        {"data": data_schema},  # Replace generic with resource schema
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
