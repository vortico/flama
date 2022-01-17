import datetime
import enum
import inspect
import typing
import uuid

from flama import http, schemas

try:
    from sqlalchemy import Table
except Exception:  # pragma: no cover
    Table = typing.Any

try:
    from databases import Database
except Exception:  # pragma: no cover
    Database = typing.Any

__all__ = [
    "OptInt",
    "OptStr",
    "OptBool",
    "OptFloat",
    "OptUUID",
    "OptDate",
    "OptDateTime",
    "OptTime",
    "Model",
    "PrimaryKey",
    "ResourceMeta",
    "ResourceMethodMeta",
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


class PrimaryKey(typing.NamedTuple):
    name: str
    type: typing.Any


class Model(typing.NamedTuple):
    table: Table
    primary_key: PrimaryKey


class ResourceMeta(typing.NamedTuple):
    model: Model
    input_schema: schemas.Schema
    input_schema_name: str
    output_schema: schemas.Schema
    output_schema_name: str
    database: Database
    name: str
    verbose_name: str
    columns: typing.Sequence[str]
    order: str


class ResourceMethodMeta(typing.NamedTuple):
    path: str
    methods: typing.List[str] = ["GET"]
    name: str = None
    kwargs: typing.Dict[str, typing.Any] = {}


HTTPMethod = enum.Enum("HTTPMethod", ["GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"])

FIELDS_TYPE_MAPPING = {
    inspect.Signature.empty: str,
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
