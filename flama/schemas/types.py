import enum
import typing as t

from flama import types

__all__ = ["Field", "Schema", "JSONSchema", "ParameterLocation"]

Field = t.TypeVar("Field")
Schema = t.TypeVar("Schema")
JSONSchema = t.Dict[str, types.JSON]


class ParameterLocation(enum.Enum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()
    response = enum.auto()
