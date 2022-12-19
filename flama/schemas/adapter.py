import abc
import sys
import typing as t

from flama.schemas.types import Field, JSONSchema, Schema

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard


class Adapter(t.Generic[Schema, Field], metaclass=abc.ABCMeta):
    DEFAULT_SCHEMA_NAME = "Schema"

    @abc.abstractmethod
    def build_field(
        self,
        name: str,
        type_: t.Type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        multiple: bool = False,
        **kwargs: t.Any,
    ) -> Field:
        ...

    @t.overload
    def build_schema(
        self, *, name: t.Optional[str] = None, fields: t.Dict[str, Field]
    ) -> t.Union[Schema, t.Type[Schema]]:
        ...

    @t.overload
    def build_schema(
        self, *, name: t.Optional[str] = None, schema: t.Union[Schema, t.Type[Schema]]
    ) -> t.Union[Schema, t.Type[Schema]]:
        ...

    @t.overload
    def build_schema(
        self,
        *,
        name: t.Optional[str] = None,
        schema: t.Union[Schema, t.Type[Schema]],
        fields: t.Optional[t.Dict[str, Field]],
    ) -> t.Union[Schema, t.Type[Schema]]:
        ...

    @abc.abstractmethod
    def build_schema(
        self,
        *,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
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
    def to_json_schema(self, schema: t.Union[Schema, t.Type[Schema], Field]) -> JSONSchema:
        ...

    @abc.abstractmethod
    def unique_schema(self, schema: t.Union[Schema, t.Type[Schema]]) -> t.Union[Schema, t.Type[Schema]]:
        ...

    @abc.abstractmethod
    def is_schema(self, obj: t.Any) -> t.TypeGuard[t.Union[Schema, t.Type[Schema]]]:
        ...

    @abc.abstractmethod
    def is_field(self, obj: t.Any) -> t.TypeGuard[t.Union[Field, t.Type[Field]]]:
        ...
