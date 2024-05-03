import abc
import sys
import typing as t

from flama.types import JSONSchema
from flama.types.schema import _T_Field, _T_Schema

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard  # type: ignore


class Adapter(t.Generic[_T_Schema, _T_Field], metaclass=abc.ABCMeta):
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
    ) -> _T_Field:
        ...

    @t.overload
    @abc.abstractmethod
    def build_schema(self, *, name: t.Optional[str] = None, fields: t.Dict[str, t.Any]) -> t.Any:
        ...

    @t.overload
    @abc.abstractmethod
    def build_schema(self, *, name: t.Optional[str] = None, schema: t.Any) -> t.Any:
        ...

    @t.overload
    @abc.abstractmethod
    def build_schema(self, *, name: t.Optional[str] = None, schema: t.Any, partial: bool) -> t.Any:
        ...

    @t.overload
    @abc.abstractmethod
    def build_schema(
        self, *, name: t.Optional[str] = None, schema: t.Any, fields: t.Optional[t.Dict[str, t.Any]]
    ) -> t.Any:
        ...

    @abc.abstractmethod
    def build_schema(
        self,
        *,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Any] = None,
        fields: t.Optional[t.Dict[str, t.Any]] = None,
        partial: bool = False,
    ) -> t.Any:
        ...

    @abc.abstractmethod
    def validate(self, schema: t.Any, values: t.Dict[str, t.Any], *, partial: bool = False) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def load(self, schema: t.Any, value: t.Dict[str, t.Any]) -> _T_Schema:
        ...

    @abc.abstractmethod
    def dump(self, schema: t.Any, value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @t.overload
    @abc.abstractmethod
    def name(self, schema: t.Any) -> str:
        ...

    @t.overload
    @abc.abstractmethod
    def name(self, schema: t.Any, *, prefix: str) -> str:
        ...

    @abc.abstractmethod
    def name(self, schema: t.Any, *, prefix: t.Optional[str] = None) -> str:
        ...

    @abc.abstractmethod
    def to_json_schema(self, schema: t.Any) -> JSONSchema:
        ...

    @abc.abstractmethod
    def unique_schema(self, schema: t.Any) -> t.Any:
        ...

    @abc.abstractmethod
    def schema_fields(self, schema: t.Any) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def is_schema(
        self, obj: t.Any
    ) -> t.TypeGuard[t.Any]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        ...

    @abc.abstractmethod
    def is_field(
        self, obj: t.Any
    ) -> t.TypeGuard[t.Any]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        ...
