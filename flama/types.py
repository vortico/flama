import datetime
import enum
import typing
import uuid

from flama import http

__all__ = [
    "OptInt",
    "OptStr",
    "OptBool",
    "OptFloat",
    "OptUUID",
    "OptDate",
    "OptDateTime",
    "OptTime",
    "HTTPMethod",
    "JSON",
]

JSON = typing.Union[str, int, float, bool, None, typing.Dict[str, typing.Any], typing.List[typing.Any]]

OptInt = typing.Optional[int]
OptStr = typing.Optional[str]
OptBool = typing.Optional[bool]
OptFloat = typing.Optional[float]
OptUUID = typing.Optional[uuid.UUID]
OptDate = typing.Optional[datetime.date]
OptDateTime = typing.Optional[datetime.datetime]
OptTime = typing.Optional[datetime.time]

HTTPMethod = enum.Enum("HTTPMethod", ["GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"])

STANDARD_FIELD_TYPE_MAPPING: typing.Dict[typing.Any, typing.Any] = {
    int: int,
    float: float,
    str: str,
    bool: bool,
    uuid.UUID: uuid.UUID,
    datetime.date: datetime.date,
    datetime.datetime: datetime.datetime,
    datetime.time: datetime.time,
}

OPTIONAL_FIELD_TYPE_MAPPING: typing.Dict[typing.Any, typing.Any] = {
    OptInt: int,
    OptFloat: float,
    OptStr: str,
    OptBool: bool,
    OptUUID: uuid.UUID,
    OptDate: datetime.date,
    OptDateTime: datetime.datetime,
    OptTime: datetime.time,
}

HTTP_FIELDS_TYPE_MAPPING: typing.Dict[typing.Any, typing.Any] = {http.QueryParam: str, http.PathParam: str}

FIELDS_TYPE_MAPPING = {**STANDARD_FIELD_TYPE_MAPPING, **OPTIONAL_FIELD_TYPE_MAPPING, **HTTP_FIELDS_TYPE_MAPPING}
