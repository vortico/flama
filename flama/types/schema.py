import inspect
import sys
import typing as t

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard  # type: ignore

__all__ = ["_T_Field", "_T_Schema", "Schema", "PartialSchema"]

_T_Field = t.TypeVar("_T_Field")
_T_Schema = t.TypeVar("_T_Schema")


def _is_schema(
    obj: t.Any,
) -> t.TypeGuard[t.Type["Schema"]]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
    return inspect.isclass(obj) and issubclass(obj, Schema)


class _SchemaMeta(type):
    def __eq__(self, other) -> bool:
        return _is_schema(other) and self.schema == other.schema  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return id(self)


class Schema(dict, t.Generic[_T_Schema], metaclass=_SchemaMeta):  # type: ignore[misc]
    schema: t.ClassVar[t.Any] = None
    partial: bool = False

    def __class_getitem__(cls, schema_cls: _T_Schema):  # type: ignore[override]
        return _SchemaMeta("_SchemaAlias", (Schema,), {"schema": schema_cls})  # type: ignore[return-value]

    @staticmethod
    def is_schema(
        obj: t.Any,
    ) -> t.TypeGuard[t.Type["Schema"]]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        return _is_schema(obj)


class PartialSchema(Schema, t.Generic[_T_Schema]):
    partial = True

    def __class_getitem__(cls, schema_cls: _T_Schema):  # type: ignore[override]
        return _SchemaMeta("_SchemaAlias", (PartialSchema,), {"schema": schema_cls})  # type: ignore[return-value]
