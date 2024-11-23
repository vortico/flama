import functools
import inspect
import typing as t

from flama import http, schemas

__all__ = ["LimitOffsetMixin", "LimitOffsetResponse"]

from flama.pagination.decorators import PaginationDecoratorFactory


class LimitOffsetResponse(http.APIResponse):
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
        schema: t.Any,
        offset: t.Optional[t.Union[int, str]] = None,
        limit: t.Optional[t.Union[int, str]] = None,
        count: t.Optional[bool] = True,
        **kwargs,
    ):
        self.offset = int(offset) if offset is not None else 0
        self.limit = int(limit) if limit is not None else self.default_limit
        self.count = count
        super().__init__(schema=schema, **kwargs)

    def render(self, content: t.Sequence[t.Any]):
        init = self.offset
        end = self.offset + self.limit
        return super().render(
            {
                "meta": {"limit": self.limit, "offset": self.offset, "count": len(content) if self.count else None},
                "data": content[init:end],
            }
        )


class LimitOffsetDecoratorFactory(PaginationDecoratorFactory):
    PARAMETERS = [
        inspect.Parameter(
            name="limit", default=None, annotation=t.Optional[int], kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        ),
        inspect.Parameter(
            name="offset", default=None, annotation=t.Optional[int], kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
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
            limit: t.Optional[int] = None,
            offset: t.Optional[int] = None,
            count: t.Optional[bool] = False,
            **kwargs,
        ):
            return LimitOffsetResponse(
                schema=schema, limit=limit, offset=offset, count=count, content=await func(*args, **kwargs)
            )

        return decorator

    @classmethod
    def _decorate_sync(cls, func: t.Callable, schema: t.Any) -> t.Callable:
        @functools.wraps(func)
        def decorator(
            *args,
            limit: t.Optional[int] = None,
            offset: t.Optional[int] = None,
            count: t.Optional[bool] = False,
            **kwargs,
        ):
            return LimitOffsetResponse(
                schema=schema, limit=limit, offset=offset, count=count, content=func(*args, **kwargs)
            )

        return decorator


class LimitOffsetMixin:
    def _paginate_limit_offset(self, func: t.Callable) -> t.Callable:
        """
        Decorator for adding pagination behavior to a view. That decorator produces a view based on limit-offset and
        it adds three query parameters to control the pagination: limit, offset and count. Offset has a default value of
        zero to start with the first element of the collection, limit default value is defined in
        :class:`LimitOffsetResponse` and count defines if the response will
        define the total number of elements.

        The output field is also modified by :class:`LimitOffsetSchema`,
        creating a new field based on it but using the old output field as the content of its data field.

        :param schema_name: Name used for output field.
        :return: Decorated view.
        """
        schema_wrapped = schemas.Schema.from_type(inspect.signature(func).return_annotation)
        resource_schema = schema_wrapped.unique_schema
        schema_name = schema_wrapped.name

        try:
            schema_module, schema_class = schema_name.rsplit(".", 1)
            paginated_schema_name = f"{schema_module}.LimitOffsetPaginated{schema_class}"
        except ValueError:  # pragma: no cover
            paginated_schema_name = f"LimitOffsetPaginated{schema_name}"
        schema = schemas.Schema.build(
            paginated_schema_name,
            schema=schemas.schemas.LimitOffset,
            fields=[schemas.Field("data", resource_schema, multiple=True)],
        ).unique_schema

        decorator = LimitOffsetDecoratorFactory.decorate(func, schema)

        self.schemas.update({schema_name: resource_schema, paginated_schema_name: schema})  # type: ignore[attr-defined]

        return decorator
