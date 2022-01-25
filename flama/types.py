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
]

OptInt = typing.Optional[int]
OptStr = typing.Optional[str]
OptBool = typing.Optional[bool]
OptFloat = typing.Optional[float]
OptUUID = typing.Optional[uuid.UUID]
OptDate = typing.Optional[datetime.date]
OptDateTime = typing.Optional[datetime.datetime]
OptTime = typing.Optional[datetime.time]

HTTPMethod = enum.Enum("HTTPMethod", ["GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"])

FIELDS_TYPE_MAPPING = {
    int: int,
    float: float,
    str: str,
    bool: bool,
    uuid.UUID: uuid.UUID,
    datetime.date: datetime.date,
    datetime.datetime: datetime.datetime,
    datetime.time: datetime.time,
    OptInt: int,
    OptFloat: float,
    OptStr: str,
    OptBool: bool,
    OptUUID: uuid.UUID,
    OptDate: datetime.date,
    OptDateTime: datetime.datetime,
    OptTime: datetime.time,
    http.QueryParam: str,
    http.PathParam: str,
}
