import typing

from flama import schemas

try:
    from sqlalchemy import Table
except Exception:  # pragma: no cover
    Table = typing.Any

try:
    from databases import Database
except Exception:  # pragma: no cover
    Database = typing.Any

__all__ = [
    "Model",
    "PrimaryKey",
    "ResourceMeta",
    "ResourceMethodMeta",
]


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
