import typing

import marshmallow

from flama.responses import APIResponse

__all__ = ["PageNumberSchema", "PageNumberResponse"]


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
