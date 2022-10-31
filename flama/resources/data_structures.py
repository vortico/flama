import dataclasses
import typing

try:
    from sqlalchemy import Table
except Exception:  # pragma: no cover
    Table = typing.Any

__all__ = ["Model", "PrimaryKey", "Schema", "Metadata", "MethodMetadata"]


@dataclasses.dataclass
class PrimaryKey:
    name: str
    type: type


@dataclasses.dataclass
class Model:
    table: Table
    primary_key: PrimaryKey


@dataclasses.dataclass
class Schema:
    name: str
    schema: typing.Any


@dataclasses.dataclass
class Schemas:
    input: Schema
    output: Schema


@dataclasses.dataclass
class Metadata:
    name: typing.Optional[str] = None
    verbose_name: typing.Optional[str] = None
    namespaces: typing.Dict[str, typing.Dict[str, typing.Any]] = dataclasses.field(default_factory=dict)

    def to_plain_dict(self) -> typing.Dict[str, typing.Any]:
        return {
            "name": self.name,
            "verbose_name": self.verbose_name,
            **{f"{namespace}_{k}": v for namespace, values in self.namespaces.items() for k, v in values.items()},
        }


@dataclasses.dataclass
class MethodMetadata:
    path: str
    methods: typing.Set[str] = dataclasses.field(default_factory=lambda: {"GET"})
    name: typing.Optional[str] = None
    kwargs: typing.Dict[str, typing.Any] = dataclasses.field(default_factory=dict)
