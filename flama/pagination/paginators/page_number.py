import functools
import inspect
import typing as t

from flama import schemas
from flama.pagination.paginators.base import BasePaginator, PaginatedResponse
from flama.schemas.data_structures import Field, Schema

__all__ = ["PageNumberPaginator", "PageNumberResponse"]

P = t.ParamSpec("P")
R = t.TypeVar("R", covariant=True)


class PageNumberResponse(PaginatedResponse[R]):
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
        schema: R,
        page: int | str | None = None,
        page_size: int | str | None = None,
        count: bool | None = True,
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


class PageNumberPaginator(BasePaginator):
    PARAMETERS = [
        inspect.Parameter(
            name="page", default=None, annotation=int | None, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        ),
        inspect.Parameter(
            name="page_size", default=None, annotation=int | None, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        ),
        inspect.Parameter(
            name="count", default=False, annotation=bool | None, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        ),
    ]

    @classmethod
    def _decorate_async(
        cls, func: t.Callable[P, t.Coroutine[R, t.Any, t.Any]], schema: t.Any
    ) -> t.Callable[P, t.Coroutine[PageNumberResponse[R], t.Any, t.Any]]:
        @functools.wraps(func)
        async def decorator(
            *args,
            page: int | None = None,
            page_size: int | None = None,
            count: bool | None = False,
            **kwargs,
        ):
            return PageNumberResponse(
                schema=schema, page=page, page_size=page_size, count=count, content=await func(*args, **kwargs)
            )

        return decorator

    @classmethod
    def _decorate_sync(cls, func: t.Callable[P, R], schema: t.Any) -> t.Callable[P, PageNumberResponse[R]]:
        @functools.wraps(func)
        def decorator(
            *args,
            page: int | None = None,
            page_size: int | None = None,
            count: bool | None = False,
            **kwargs,
        ):
            return PageNumberResponse(
                schema=schema, page=page, page_size=page_size, count=count, content=func(*args, **kwargs)
            )

        return decorator

    @classmethod
    def wraps(
        cls, func: t.Callable[P, R | t.Coroutine[R, t.Any, t.Any]], signature: inspect.Signature
    ) -> tuple[t.Callable[P, R | t.Coroutine[R, t.Any, t.Any]], dict[str, t.Any]]:
        """
        Decorator for adding pagination behavior to a view. That decorator produces a view based on page numbering and
        it adds three query parameters to control the pagination: page, page_size and count. Page has a default value of
        first page, page_size default value is defined in
        :class:`PageNumberResponse` and count defines if the response will define
        the total number of elements.

        The output field is also modified by :class:`PageNumberSchema`, creating
        a new field based on it but using the old output field as the content of its data field.

        :param func: Function to decorate.
        :param signature: Function signature.
        :return: Decorated view and new schemas.
        """
        schema = Schema.from_type(signature.return_annotation)

        try:
            module, schema_class = schema.name.rsplit(".", 1)
            name = f"PageNumberPaginated{schema_class}"
        except ValueError:  # pragma: no cover
            module = None
            name = f"PageNumberPaginated{schema.name}"

        paginated_schema = Schema.build(
            name,
            module,
            schema=schemas.schemas.PageNumber,
            fields=[Field("data", schema.unique_schema, multiple=True)],
        )

        decorator = cls._decorate(func, signature, paginated_schema.unique_schema)
        new_schemas = {schema.name: schema.unique_schema, paginated_schema.name: paginated_schema.unique_schema}

        return decorator, new_schemas
