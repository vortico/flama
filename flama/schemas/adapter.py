import abc
import typing as t

from flama.types import JSONSchema

__all__ = ["Adapter"]

_T_Field = t.TypeVar("_T_Field")
_T_Schema = t.TypeVar("_T_Schema")


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
    ) -> _T_Field: ...

    @t.overload
    @abc.abstractmethod
    def build_schema(
        self, *, name: str | None = None, module: str | None = None, fields: dict[str, t.Any]
    ) -> t.Any: ...

    @t.overload
    @abc.abstractmethod
    def build_schema(self, *, name: str | None = None, module: str | None = None, schema: t.Any) -> t.Any: ...

    @t.overload
    @abc.abstractmethod
    def build_schema(
        self, *, name: str | None = None, module: str | None = None, schema: t.Any, partial: bool
    ) -> t.Any: ...

    @t.overload
    @abc.abstractmethod
    def build_schema(
        self,
        *,
        name: str | None = None,
        module: str | None = None,
        schema: t.Any,
        fields: dict[str, t.Any] | None,
    ) -> t.Any: ...

    @abc.abstractmethod
    def build_schema(
        self,
        *,
        name: str | None = None,
        module: str | None = None,
        schema: t.Any | None = None,
        fields: dict[str, t.Any] | None = None,
        partial: bool = False,
    ) -> t.Any: ...

    @abc.abstractmethod
    def validate(self, schema: t.Any, values: dict[str, t.Any], *, partial: bool = False) -> dict[str, t.Any]: ...

    @abc.abstractmethod
    def load(self, schema: t.Any, value: dict[str, t.Any]) -> _T_Schema: ...

    @abc.abstractmethod
    def dump(self, schema: t.Any, value: dict[str, t.Any]) -> dict[str, t.Any]: ...

    @t.overload
    @abc.abstractmethod
    def name(self, schema: t.Any) -> str: ...

    @t.overload
    @abc.abstractmethod
    def name(self, schema: t.Any, *, prefix: str) -> str: ...

    @abc.abstractmethod
    def name(self, schema: t.Any, *, prefix: str | None = None) -> str: ...

    @abc.abstractmethod
    def to_json_schema(self, schema: t.Any) -> JSONSchema: ...

    @abc.abstractmethod
    def unique_schema(self, schema: t.Any) -> t.Any: ...

    @abc.abstractmethod
    def schema_fields(self, schema: t.Any) -> dict[str, t.Any]: ...

    @abc.abstractmethod
    def is_schema(self, obj: t.Any) -> t.TypeGuard[t.Any]: ...

    @abc.abstractmethod
    def is_field(self, obj: t.Any) -> t.TypeGuard[t.Any]: ...
