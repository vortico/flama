import typing

try:
    from sqlalchemy import Table
except Exception:  # pragma: no cover
    Table = typing.Any

__all__ = [
    "Model",
    "PrimaryKey",
    "Schema",
    "Metadata",
    "MethodMetadata",
]


class PrimaryKey(typing.NamedTuple):
    name: str
    type: type


class Model(typing.NamedTuple):
    table: Table
    primary_key: PrimaryKey


class Schema(typing.NamedTuple):
    name: str
    schema: typing.Any


class Schemas(typing.NamedTuple):
    input: Schema
    output: Schema


class Metadata(typing.NamedTuple):
    model: Model
    schemas: Schemas
    name: str
    verbose_name: str
    columns: typing.Sequence[str]
    order: str


class MethodMetadata(typing.NamedTuple):
    path: str
    methods: typing.List[str] = ["GET"]
    name: typing.Optional[str] = None
    kwargs: typing.Dict[str, typing.Any] = {}
