import datetime
import typing as t
import uuid

from flama.types.http import PathParam, QueryParam
from flama.types.schema import OptBool, OptDate, OptDateTime, OptFloat, OptInt, OptStr, OptTime, OptUUID

__all__ = [
    "STANDARD_FIELD_TYPE_MAPPING",
    "OPTIONAL_FIELD_TYPE_MAPPING",
    "HTTP_FIELDS_TYPE_MAPPING",
    "FIELDS_TYPE_MAPPING",
]


STANDARD_FIELD_TYPE_MAPPING: t.Dict[t.Any, t.Any] = {
    int: int,
    float: float,
    str: str,
    bool: bool,
    uuid.UUID: uuid.UUID,
    datetime.date: datetime.date,
    datetime.datetime: datetime.datetime,
    datetime.time: datetime.time,
}

OPTIONAL_FIELD_TYPE_MAPPING: t.Dict[t.Any, t.Any] = {
    OptInt: int,
    OptFloat: float,
    OptStr: str,
    OptBool: bool,
    OptUUID: uuid.UUID,
    OptDate: datetime.date,
    OptDateTime: datetime.datetime,
    OptTime: datetime.time,
}

HTTP_FIELDS_TYPE_MAPPING: t.Dict[t.Any, t.Any] = {QueryParam: str, PathParam: str}

FIELDS_TYPE_MAPPING = {**STANDARD_FIELD_TYPE_MAPPING, **OPTIONAL_FIELD_TYPE_MAPPING, **HTTP_FIELDS_TYPE_MAPPING}
