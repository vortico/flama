import dataclasses
import typing as t

__all__ = [
    "_T_Field",
    "_T_Schema",
    "SchemaType",
    "SchemaMetadata",
    "get_schema_metadata",
    "is_schema",
    "is_schema_partial",
    "is_schema_multiple",
]

_T_Field = t.TypeVar("_T_Field")
_T_Schema = t.TypeVar("_T_Schema")

SchemaType = dict[str, t.Any]


@dataclasses.dataclass(frozen=True)
class SchemaMetadata:
    schema: t.Any
    partial: bool = False
    multiple: bool = False


def get_schema_metadata(obj: t.Any) -> SchemaMetadata:
    return getattr(obj, "__metadata__", [None])[0]


def is_schema(obj: t.Any) -> bool:
    return isinstance(get_schema_metadata(obj), SchemaMetadata)


def is_schema_partial(obj: t.Any) -> bool:
    return is_schema(obj) and get_schema_metadata(obj).partial


def is_schema_multiple(obj: t.Any) -> bool:
    return is_schema(obj) and get_schema_metadata(obj).multiple
