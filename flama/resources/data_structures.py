import dataclasses
import inspect
import typing as t

from flama import types

try:
    from sqlalchemy import Table
except Exception:  # pragma: no cover
    Table = t.Any

if t.TYPE_CHECKING:
    from flama.resources.resource import Resource

__all__ = ["Model", "PrimaryKey", "Schema", "Metadata", "_ResourceMethodMetadata", "ResourceMethod"]


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
class _ResourceMethodMetadata:
    path: str
    methods: set[str] = dataclasses.field(default_factory=lambda: {"GET"})
    name: str | None = None
    include_in_schema: bool = True
    pagination: types.Pagination | None = None
    tags: dict[str, t.Any] | None = None


@dataclasses.dataclass
class _ResourceMethodFunction:
    method: t.Callable
    name: str = dataclasses.field(init=False)
    signature: inspect.Signature = dataclasses.field(init=False)

    def __post_init__(self):
        self.name = self.method.__name__
        self.signature = inspect.signature(self.method)


@dataclasses.dataclass
class ResourceMethod:
    meta: _ResourceMethodMetadata = dataclasses.field(init=False)
    func: _ResourceMethodFunction = dataclasses.field(init=False)

    method: dataclasses.InitVar[t.Callable]
    path: dataclasses.InitVar[str]
    methods: dataclasses.InitVar[set[str] | None] = None
    name: dataclasses.InitVar[str | None] = None
    include_in_schema: dataclasses.InitVar[bool] = True
    pagination: dataclasses.InitVar[types.Pagination | None] = None
    tags: dataclasses.InitVar[dict[str, t.Any] | None] = None

    def __post_init__(
        self,
        method: t.Callable,
        path: str,
        methods: set[str] | None = None,
        name: str | None = None,
        include_in_schema: bool = True,
        pagination: types.Pagination | None = None,
        tags: dict[str, t.Any] | None = None,
    ):
        self.meta = _ResourceMethodMetadata(
            path=path,
            methods=methods if methods is not None else {"GET"},
            name=name,
            include_in_schema=include_in_schema,
            pagination=pagination,
            tags=tags,
        )
        self.func = _ResourceMethodFunction(method=method)

    def get_method(self, resource: "Resource") -> t.Callable:
        return getattr(resource, self.func.name)
