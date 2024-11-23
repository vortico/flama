import abc
import asyncio
import inspect
import typing as t


class PaginationDecoratorFactory:
    PARAMETERS: list[inspect.Parameter]

    @classmethod
    def decorate(cls, func: t.Callable, schema: t.Any) -> t.Callable:
        func_signature = inspect.signature(func)
        if "kwargs" not in func_signature.parameters:
            raise TypeError("Paginated views must define **kwargs param")

        decorated_func = (
            cls._decorate_async(func, schema) if asyncio.iscoroutinefunction(func) else cls._decorate_sync(func, schema)
        )

        decorated_func.__signature__ = inspect.Signature(  # type: ignore
            parameters=[
                *[v for k, v in func_signature.parameters.items() if k != "kwargs"],
                *cls.PARAMETERS,
            ],
            return_annotation=schema,
        )

        return decorated_func

    @classmethod
    @abc.abstractmethod
    def _decorate_async(cls, func: t.Callable, schema: t.Any) -> t.Callable:
        ...

    @classmethod
    @abc.abstractmethod
    def _decorate_sync(cls, func: t.Callable, schema: t.Any) -> t.Callable:
        ...
