import dataclasses
import typing as t

try:
    from sqlalchemy import Table
except Exception:  # pragma: no cover
    Table = t.Any

__all__ = ["Model", "PrimaryKey", "Schema", "Metadata", "MethodMetadata"]


@dataclasses.dataclass
class PrimaryKey:
    name: str
    type: type


@dataclasses.dataclass
class Model:
    table: Table  # type: ignore
    primary_key: PrimaryKey


@dataclasses.dataclass
class Schema:
    name: str
    schema: t.Any


@dataclasses.dataclass
class Schemas:
    input: Schema
    output: Schema


@dataclasses.dataclass
class Metadata:
    name: str = dataclasses.field(init=False)
    verbose_name: str = dataclasses.field(init=False)
    namespaces: dict[str, dict[str, t.Any]] = dataclasses.field(default_factory=dict)

    def to_plain_dict(self) -> dict[str, t.Any]:
        return {
            "name": self.name,
            "verbose_name": self.verbose_name,
            **{f"{namespace}_{k}": v for namespace, values in self.namespaces.items() for k, v in values.items()},
        }


@dataclasses.dataclass
class MethodMetadata:
    path: str
    methods: set[str] = dataclasses.field(default_factory=lambda: {"GET"})
    name: t.Optional[str] = None
    tags: dict[str, t.Any] = dataclasses.field(default_factory=dict)
