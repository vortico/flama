import abc
import dataclasses
import typing as t

from flama import _compat

if t.TYPE_CHECKING:
    from flama.schemas._libs.marshmallow import Schema as MarshmallowSchema
    from flama.schemas._libs.pydantic import Schema as PydanticSchema

__all__ = [
    "Output",
    "OutputList",
    "Schema",
    "SchemaList",
    "SchemaMetadata",
    "SchemaResponse",
    "get_schema_metadata",
    "is_schema",
    "is_schema_partial",
]

# Without a schema library installed its name is unknown to type checkers, which then accept any schema.
SchemaModel = t.TypeVar("SchemaModel", bound="PydanticSchema | MarshmallowSchema")
SchemaPayload = t.TypeVar(
    "SchemaPayload",
    bound="PydanticSchema | MarshmallowSchema | t.Sequence[PydanticSchema | MarshmallowSchema]",
)


@dataclasses.dataclass(frozen=True)
class SchemaMetadata:
    schema: t.Any
    partial: bool = False


class SchemaResponse(abc.ABC, t.Generic[SchemaPayload]):
    """A response whose body is the payload of a schema, as ``flama.http.APIResponse`` is.

    It lets annotations name such a response without importing ``flama.http``.
    """


Schema = _compat.TypeAliasType("Schema", dict[str, t.Any], type_params=(SchemaModel,))
SchemaList = _compat.TypeAliasType("SchemaList", list[Schema[SchemaModel]], type_params=(SchemaModel,))
Output = _compat.TypeAliasType("Output", Schema[SchemaModel] | SchemaResponse[SchemaModel], type_params=(SchemaModel,))
OutputList = _compat.TypeAliasType(
    "OutputList", SchemaList[SchemaModel] | SchemaResponse[list[SchemaModel]], type_params=(SchemaModel,)
)

_ALIASES = (Schema, SchemaList, Output, OutputList)


def get_schema_metadata(obj: t.Any) -> SchemaMetadata | None:
    """The schema an annotation is marked with.

    The schema aliases are marked with the schema they are subscripted with, and annotated with the schema itself
    as with ``SchemaMetadata(schema)``.

    :param obj: Annotation to inspect.
    :return: The schema metadata, or None when the annotation is not marked with a schema.
    """
    if t.get_origin(obj) in _ALIASES:
        (schema,) = t.get_args(obj)
        return None if isinstance(schema, t.TypeVar) else SchemaMetadata(schema)

    if t.get_origin(obj) is not t.Annotated:
        return None

    type_, metadata, *_ = t.get_args(obj)
    if isinstance(metadata, SchemaMetadata):
        return metadata

    return SchemaMetadata(metadata) if type_ in _ALIASES else None


def is_schema(obj: t.Any) -> bool:
    return get_schema_metadata(obj) is not None


def is_schema_partial(obj: t.Any) -> bool:
    return (metadata := get_schema_metadata(obj)) is not None and metadata.partial
