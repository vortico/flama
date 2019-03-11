import datetime
import enum
import typing
import uuid

import marshmallow

__all__ = ["FieldLocation", "Field", "EndpointInfo", "OptInt", "OptStr", "OptBool", "OptFloat"]


class FieldLocation(enum.Enum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()


class Field(typing.NamedTuple):
    name: str
    location: FieldLocation
    schema: typing.Union[marshmallow.fields.Field, marshmallow.Schema]
    required: bool = False


class EndpointInfo(typing.NamedTuple):
    path: str
    method: str
    func: typing.Callable
    query_fields: typing.Dict[str, Field]
    path_fields: typing.Dict[str, Field]
    body_field: Field
    output_field: typing.Any


OptInt = typing.Optional[int]
OptStr = typing.Optional[str]
OptBool = typing.Optional[bool]
OptFloat = typing.Optional[float]
OptUUID = typing.Optional[uuid.UUID]
OptDate = typing.Optional[datetime.date]
OptDateTime = typing.Optional[datetime.datetime]
