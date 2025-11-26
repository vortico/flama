import abc
import inspect
import typing as t

from flama import http

__all__ = ["BasePaginator", "PaginatedResponse"]

P = t.ParamSpec("P")
R = t.TypeVar("R", covariant=True)


class PaginatedResponse(t.Generic[R], abc.ABC, http.APIResponse):
    def __init__(self, schema: R, **kwargs):
        super().__init__(schema=schema, **kwargs)


class BasePaginator(abc.ABC):
    PARAMETERS: list[inspect.Parameter]

    @classmethod
    def _decorate(
        cls, func: t.Callable[P, R | t.Coroutine[R, t.Any, t.Any]], signature: inspect.Signature, schema: t.Any
    ) -> t.Callable[P, R | t.Coroutine[R, t.Any, t.Any]]:
        if "kwargs" not in signature.parameters:
            raise TypeError("Paginated views must define **kwargs param")

        decorated_func = (
            cls._decorate_async(func, schema) if inspect.iscoroutinefunction(func) else cls._decorate_sync(func, schema)
        )

        decorated_func.__signature__ = inspect.Signature(  # type: ignore
            parameters=[
                *[v for k, v in signature.parameters.items() if k != "kwargs"],
                *cls.PARAMETERS,
            ],
            return_annotation=schema,
        )

        return decorated_func

    @classmethod
    @abc.abstractmethod
    def _decorate_async(
        cls, func: t.Callable[P, t.Coroutine[R, t.Any, t.Any]], schema: t.Any
    ) -> t.Callable[P, t.Coroutine[R, t.Any, t.Any]]: ...

    @classmethod
    @abc.abstractmethod
    def _decorate_sync(cls, func: t.Callable[P, R], schema: t.Any) -> t.Callable[P, R]: ...

    @classmethod
    @abc.abstractmethod
    def wraps(
        cls, func: t.Callable[P, R | t.Coroutine[R, t.Any, t.Any]], signature: inspect.Signature
    ) -> tuple[t.Callable[P, R | t.Coroutine[R, t.Any, t.Any]], dict[str, t.Any]]:
        """
        Decorator for adding pagination behavior to a view.

        :param func: Function to decorate.
        :param signature: Function signature.
        :return: Decorated view and new schemas.
        """
        ...
