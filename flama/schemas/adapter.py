import abc
import sys
import typing as t

from flama.schemas.types import Field, Schema

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard
else:  # pragma: no cover
    from typing_extensions import TypeGuard


class Adapter(t.Generic[Schema, Field], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def build_field(
        self,
        name: str,
        type: t.Type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        **kwargs: t.Any
    ) -> Field:
        ...

    @abc.abstractmethod
    def build_schema(
        self,
        name: str = "Schema",
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        pagination: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        paginated_schema_name: t.Optional[str] = None,
        fields: t.Optional[t.Dict[str, Field]] = None,
    ) -> t.Union[Schema, t.Type[Schema]]:
        ...

    @abc.abstractmethod
    def validate(self, schema: t.Union[Schema, t.Type[Schema]], values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def load(self, schema: t.Union[Schema, t.Type[Schema]], value: t.Dict[str, t.Any]) -> Schema:
        ...

    @abc.abstractmethod
    def dump(self, schema: t.Union[Schema, t.Type[Schema]], value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def to_json_schema(self, schema: t.Union[Schema, t.Type[Schema], Field]) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def unique_schema(self, schema: Schema) -> t.Union[Schema, t.Type[Schema]]:
        ...

    @abc.abstractmethod
    def is_schema(self, obj: t.Any) -> TypeGuard[t.Union[Schema, t.Type[Schema]]]:
        ...

    @abc.abstractmethod
    def is_field(self, obj: t.Any) -> TypeGuard[t.Union[Field, t.Type[Field]]]:
        ...
