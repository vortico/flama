import functools
import inspect
import typing as t

from flama import http, schemas

__all__ = ["PageNumberMixin", "PageNumberResponse"]

from flama.pagination.decorators import PaginationDecoratorFactory


class PageNumberResponse(http.APIResponse):
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
        schema: t.Any,
        page: t.Optional[t.Union[int, str]] = None,
        page_size: t.Optional[t.Union[int, str]] = None,
        count: t.Optional[bool] = True,
        **kwargs,
    ):
        self.page_number = int(page) if page is not None else 1
        self.page_size = int(page_size) if page_size is not None else self.default_page_size
        self.count = count
        super().__init__(schema=schema, **kwargs)

    def render(self, content: t.Sequence[t.Any]):
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


class PageNumberDecoratorFactory(PaginationDecoratorFactory):
    PARAMETERS = [
        inspect.Parameter(
            name="page", default=None, annotation=t.Optional[int], kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        ),
        inspect.Parameter(
            name="page_size", default=None, annotation=t.Optional[int], kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        ),
        inspect.Parameter(
            name="count", default=False, annotation=t.Optional[bool], kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        ),
    ]

    @classmethod
    def _decorate_async(cls, func: t.Callable, schema: t.Any) -> t.Callable:
        @functools.wraps(func)
        async def decorator(
            *args,
            page: t.Optional[int] = None,
            page_size: t.Optional[int] = None,
            count: t.Optional[bool] = False,
            **kwargs,
        ):
            return PageNumberResponse(
                schema=schema, page=page, page_size=page_size, count=count, content=await func(*args, **kwargs)
            )

        return decorator

    @classmethod
    def _decorate_sync(cls, func: t.Callable, schema: t.Any) -> t.Callable:
        @functools.wraps(func)
        def decorator(
            *args,
            page: t.Optional[int] = None,
            page_size: t.Optional[int] = None,
            count: t.Optional[bool] = False,
            **kwargs,
        ):
            return PageNumberResponse(
                schema=schema, page=page, page_size=page_size, count=count, content=func(*args, **kwargs)
            )

        return decorator


class PageNumberMixin:
    def _paginate_page_number(self, func: t.Callable) -> t.Callable:
        """
        Decorator for adding pagination behavior to a view. That decorator produces a view based on page numbering and
        it adds three query parameters to control the pagination: page, page_size and count. Page has a default value of
        first page, page_size default value is defined in
        :class:`PageNumberResponse` and count defines if the response will define
        the total number of elements.

        The output field is also modified by :class:`PageNumberSchema`, creating
        a new field based on it but using the old output field as the content of its data field.

        :param schema_name: Name used for output field.
        :return: Decorated view.
        """
        schema_wrapped = schemas.Schema.from_type(inspect.signature(func).return_annotation)
        resource_schema = schema_wrapped.unique_schema
        schema_name = schema_wrapped.name

        try:
            schema_module, schema_class = schema_name.rsplit(".", 1)
            paginated_schema_name = f"{schema_module}.PageNumberPaginated{schema_class}"
        except ValueError:  # pragma: no cover
            paginated_schema_name = f"PageNumberPaginated{schema_name}"
        schema = schemas.Schema.build(
            paginated_schema_name,
            schema=schemas.schemas.PageNumber,
            fields=[schemas.Field("data", resource_schema, multiple=True)],
        ).unique_schema

        decorator = PageNumberDecoratorFactory.decorate(func, schema)

        self.schemas.update({schema_name: resource_schema, paginated_schema_name: schema})  # type: ignore[attr-defined]

        return decorator
