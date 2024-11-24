import abc
import typing as t

from flama import compat
from flama.schemas.types import _T_Field, _T_Schema
from flama.types import JSONSchema

__all__ = ["Adapter"]


class Adapter(t.Generic[_T_Schema, _T_Field], metaclass=abc.ABCMeta):
    DEFAULT_SCHEMA_NAME = "Schema"

    @abc.abstractmethod
    def build_field(
        self,
        name: str,
        type_: type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        multiple: bool = False,
        **kwargs: t.Any,
    ) -> _T_Field:
        ...

    @t.overload
    @abc.abstractmethod
    def build_schema(self, *, name: t.Optional[str] = None, fields: dict[str, t.Any]) -> t.Any:
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
        self, *, name: t.Optional[str] = None, schema: t.Any, fields: t.Optional[dict[str, t.Any]]
    ) -> t.Any:
        ...

    @abc.abstractmethod
    def build_schema(
        self,
        *,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Any] = None,
        fields: t.Optional[dict[str, t.Any]] = None,
        partial: bool = False,
    ) -> t.Any:
        ...

    @abc.abstractmethod
    def validate(self, schema: t.Any, values: dict[str, t.Any], *, partial: bool = False) -> dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def load(self, schema: t.Any, value: dict[str, t.Any]) -> _T_Schema:
        ...

    @abc.abstractmethod
    def dump(self, schema: t.Any, value: dict[str, t.Any]) -> dict[str, t.Any]:
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
    def schema_fields(self, schema: t.Any) -> dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def is_schema(self, obj: t.Any) -> compat.TypeGuard[t.Any]:  # PORT: Replace compat when stop supporting 3.9
        ...

    @abc.abstractmethod
    def is_field(self, obj: t.Any) -> compat.TypeGuard[t.Any]:  # PORT: Replace compat when stop supporting 3.9
        ...
