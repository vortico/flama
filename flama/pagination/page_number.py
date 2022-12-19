import asyncio
import functools
import inspect
import typing as t

from flama import http, schemas

try:
    import forge
except Exception:  # pragma: no cover
    forge = None  # type: ignore

__all__ = ["PageNumberMixin", "PageNumberResponse"]


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
        schema: "schemas.types.Schema",
        page: t.Optional[t.Union[int, str]] = None,
        page_size: t.Optional[t.Union[int, str]] = None,
        count: t.Optional[bool] = True,
        **kwargs
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


class PageNumberMixin:
    def page_number(self, schema_name: str):
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

        def _inner(func: t.Callable):
            assert forge is not None, "`python-forge` must be installed to use Paginator."

            resource_schema = schemas.Schema.from_type(inspect.signature(func).return_annotation).unique_schema
            paginated_schema_name = "PageNumberPaginated" + schema_name
            schema = schemas.Schema.build(
                paginated_schema_name,
                schema=schemas.schemas.PageNumber,
                fields=[schemas.Field("data", resource_schema, multiple=True)],
            ).unique_schema

            forge_revision_list = (
                forge.copy(func),
                forge.insert(forge.arg("page", default=None, type=t.Optional[int]), index=-1),
                forge.insert(forge.arg("page_size", default=None, type=t.Optional[int]), index=-1),
                forge.insert(forge.arg("count", default=True, type=bool), index=-1),
                forge.delete("kwargs"),
                forge.returns(schema),
            )

            try:
                if asyncio.iscoroutinefunction(func):

                    @forge.compose(*forge_revision_list)
                    @functools.wraps(func)
                    async def decorator(
                        *args,
                        page: t.Optional[int] = None,
                        page_size: t.Optional[int] = None,
                        count: bool = True,
                        **kwargs
                    ):
                        return PageNumberResponse(
                            schema=schema,
                            page=page,
                            page_size=page_size,
                            count=count,
                            content=await func(*args, **kwargs),
                        )

                else:

                    @forge.compose(*forge_revision_list)
                    @functools.wraps(func)
                    def decorator(
                        *args,
                        page: t.Optional[int] = None,
                        page_size: t.Optional[int] = None,
                        count: bool = True,
                        **kwargs
                    ):
                        return PageNumberResponse(
                            schema=schema, page=page, page_size=page_size, count=count, content=func(*args, **kwargs)
                        )

            except ValueError as e:
                raise TypeError("Paginated views must define **kwargs param") from e
            else:
                self.schemas.update(  # type: ignore[attr-defined]
                    {schema_name: resource_schema, paginated_schema_name: schema}
                )
            return decorator

        return _inner
