import enum
import typing

__all__ = ["Field", "Schema", "ParameterLocation"]


Field = typing.TypeVar("Field")
Schema = typing.TypeVar("Schema")


class ParameterLocation(enum.Enum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()
    response = enum.auto()
