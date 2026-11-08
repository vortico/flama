import abc
import dataclasses
import typing as t

if t.TYPE_CHECKING:
    from flama.schemas._libs.marshmallow import Schema as MarshmallowSchema
    from flama.schemas._libs.pydantic import Schema as PydanticSchema

__all__ = [
    "Schema",
    "SchemaList",
    "SchemaMetadata",
    "SchemaResponse",
    "get_schema_metadata",
    "is_schema",
    "is_schema_partial",
]

# Without a schema library installed its name is unknown to type checkers, which then accept any payload.
SchemaPayload = t.TypeVar(
    "SchemaPayload",
    bound="PydanticSchema | MarshmallowSchema | t.Sequence[PydanticSchema | MarshmallowSchema]",
)

Schema: t.TypeAlias = dict[str, t.Any]
SchemaList: t.TypeAlias = list[Schema]


@dataclasses.dataclass(frozen=True)
class SchemaMetadata:
    schema: t.Any
    partial: bool = False


class SchemaResponse(abc.ABC, t.Generic[SchemaPayload]):
    """A response whose body is the payload of a schema, as ``flama.http.APIResponse`` is.

    It lets annotations name such a response without importing ``flama.http``.
    """


def get_schema_metadata(obj: t.Any) -> SchemaMetadata | None:
    """The schema an annotation is marked with.

    A ``Schema`` or ``SchemaList`` annotated with the schema itself is marked as with ``SchemaMetadata(schema)``.

    :param obj: Annotation to inspect.
    :return: The schema metadata, or None when the annotation is not marked with a schema.
    """
    if t.get_origin(obj) is not t.Annotated:
        return None

    type_, metadata, *_ = t.get_args(obj)
    if isinstance(metadata, SchemaMetadata):
        return metadata

    return SchemaMetadata(metadata) if type_ in (Schema, SchemaList) else None


def is_schema(obj: t.Any) -> bool:
    return get_schema_metadata(obj) is not None


def is_schema_partial(obj: t.Any) -> bool:
    return (metadata := get_schema_metadata(obj)) is not None and metadata.partial
