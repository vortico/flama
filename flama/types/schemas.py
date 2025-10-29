import dataclasses
import typing as t

__all__ = ["Schema", "SchemaList", "SchemaMetadata", "get_schema_metadata", "is_schema", "is_schema_partial"]


Schema: t.TypeAlias = dict[str, t.Any]
SchemaList: t.TypeAlias = list[Schema]


@dataclasses.dataclass(frozen=True)
class SchemaMetadata:
    schema: t.Any
    partial: bool = False


def get_schema_metadata(obj: t.Any) -> SchemaMetadata:
    return getattr(obj, "__metadata__", [None])[0]


def is_schema(obj: t.Any) -> bool:
    return isinstance(get_schema_metadata(obj), SchemaMetadata)


def is_schema_partial(obj: t.Any) -> bool:
    return is_schema(obj) and get_schema_metadata(obj).partial
