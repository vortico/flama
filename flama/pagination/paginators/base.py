import abc
import inspect
import typing as t

from flama import concurrency, exceptions, schemas, types
from flama._core.json_encoder import encode_json
from flama.http.responses.response import BufferedResponse
from flama.schemas.data_structures import Schema

__all__ = ["BasePaginator", "PaginatedResponse"]

SchemaType = t.TypeVar("SchemaType", bound=type, covariant=True)
P = t.ParamSpec("P")


class PaginatedResponse(BufferedResponse[t.Sequence[types.JSONSchema]], t.Generic[SchemaType]):
    media_type = "application/json"

    def __init__(self, *args, schema: SchemaType, **kwargs):
        self.schema = schema
        super().__init__(*args, **kwargs)

    def _encode_content(self, content: types.JSONSchema, /) -> bytes:
        try:
            content = Schema.from_type(self.schema).dump(content)
        except schemas.SchemaValidationError as e:
            raise exceptions.SerializationError(status_code=500, detail=e.errors)

        return encode_json(content)


class BasePaginator(abc.ABC):
    PARAMETERS: list[inspect.Parameter]

    @t.overload
    @classmethod
    def _decorate(
        cls, func: t.Callable[P, SchemaType], signature: inspect.Signature, schema: SchemaType
    ) -> t.Callable[P, PaginatedResponse[SchemaType]]: ...
    @t.overload
    @classmethod
    def _decorate(
        cls,
        func: t.Callable[P, t.Coroutine[SchemaType, t.Any, t.Any]],
        signature: inspect.Signature,
        schema: SchemaType,
    ) -> t.Callable[P, t.Coroutine[PaginatedResponse[SchemaType], t.Any, t.Any]]: ...
    @classmethod
    def _decorate(
        cls,
        func: t.Callable[P, SchemaType | t.Coroutine[SchemaType, t.Any, t.Any]],
        signature: inspect.Signature,
        schema: SchemaType,
    ) -> t.Callable[P, PaginatedResponse[SchemaType] | t.Coroutine[PaginatedResponse[SchemaType], t.Any, t.Any]]:
        if "kwargs" not in signature.parameters:
            raise TypeError("Paginated views must define **kwargs param")

        decorated_func = (
            cls._decorate_async(func, schema) if concurrency.is_async(func) else cls._decorate_sync(func, schema)
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
        cls, func: t.Callable[P, t.Coroutine[SchemaType, t.Any, t.Any]], schema: t.Any
    ) -> t.Callable[P, t.Coroutine[PaginatedResponse[SchemaType], t.Any, t.Any]]: ...

    @classmethod
    @abc.abstractmethod
    def _decorate_sync(
        cls, func: t.Callable[P, SchemaType], schema: t.Any
    ) -> t.Callable[P, PaginatedResponse[SchemaType]]: ...

    @t.overload
    @classmethod
    @abc.abstractmethod
    def wraps(
        cls, func: t.Callable[P, SchemaType], signature: inspect.Signature
    ) -> tuple[t.Callable[P, PaginatedResponse[SchemaType]], dict[str, t.Any]]: ...
    @t.overload
    @classmethod
    @abc.abstractmethod
    def wraps(
        cls, func: t.Callable[P, t.Coroutine[SchemaType, t.Any, t.Any]], signature: inspect.Signature
    ) -> tuple[t.Callable[P, t.Coroutine[PaginatedResponse[SchemaType], t.Any, t.Any]], dict[str, t.Any]]: ...
    @classmethod
    @abc.abstractmethod
    def wraps(
        cls, func: t.Callable[P, SchemaType | t.Coroutine[SchemaType, t.Any, t.Any]], signature: inspect.Signature
    ) -> tuple[
        t.Callable[P, PaginatedResponse[SchemaType] | t.Coroutine[PaginatedResponse[SchemaType], t.Any, t.Any]],
        dict[str, t.Any],
    ]:
        """
        Decorator for adding pagination behavior to a view.

        :param func: Function to decorate.
        :param signature: Function signature.
        :return: Decorated view and new schemas.
        """
        ...
