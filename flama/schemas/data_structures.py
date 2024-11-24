import builtins
import dataclasses
import enum
import typing as t

from flama import compat, schemas, types
from flama.injection.resolver import Parameter as InjectionParameter

__all__ = ["Field", "Schema", "Parameter", "Parameters"]


UNKNOWN = t.TypeVar("UNKNOWN")


class ParameterLocation(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()
    response = enum.auto()


@dataclasses.dataclass(frozen=True)
class Field:
    name: str
    type: type
    nullable: bool = dataclasses.field(init=False)
    field: t.Any = dataclasses.field(hash=False, init=False, compare=False)
    multiple: t.Optional[bool] = dataclasses.field(hash=False, compare=False, default=None)
    required: bool = True
    default: t.Any = InjectionParameter.empty

    def __post_init__(self) -> None:
        object.__setattr__(self, "nullable", type(None) in t.get_args(self.type) or self.default is None)

        field_type = t.get_args(self.type)[0] if t.get_origin(self.type) in (t.Union, compat.UnionType) else self.type

        if not Schema.is_schema(field_type) and self.multiple is None:
            object.__setattr__(self, "multiple", t.get_origin(self.type) is list)

        object.__setattr__(
            self,
            "field",
            schemas.adapter.build_field(
                self.name,
                field_type,
                nullable=self.nullable,
                required=self.required,
                default=self.default,
                multiple=bool(self.multiple),
            ),
        )

    @classmethod
    def from_parameter(cls, parameter: InjectionParameter) -> "Field":
        return cls(
            parameter.name,
            parameter.annotation,
            required=parameter.default is InjectionParameter.empty,
            default=parameter.default
            if parameter.default is not InjectionParameter.empty
            else InjectionParameter.empty,
        )

    @classmethod
    def is_field(cls, obj: t.Any) -> bool:
        return schemas.adapter.is_field(obj)

    @classmethod
    def is_http_valid_type(cls, type_: builtins.type) -> bool:
        origin = t.get_origin(type_)
        args = t.get_args(type_)
        NoneType = type(None)

        return (
            (type_ in types.PARAMETERS_TYPES)
            or (
                origin in (t.Union, compat.UnionType)
                and len(args) == 2
                and args[0] in types.PARAMETERS_TYPES
                and args[1] is NoneType
            )
            or (origin is list and args[0] in types.PARAMETERS_TYPES)
        )

    @property
    def json_schema(self) -> types.JSONSchema:
        return schemas.adapter.to_json_schema(self.field)


@dataclasses.dataclass(frozen=True)
class Schema:
    schema: t.Any = dataclasses.field(hash=False, compare=False)

    @classmethod
    def from_type(cls, type_: t.Optional[type]) -> "Schema":
        if schemas.is_schema(type_):
            schema = schemas.get_schema_metadata(type_).schema

            if schemas.is_schema_partial(type_):
                schema = schemas.adapter.build_schema(
                    name=schemas.adapter.name(schema, prefix="Partial").rsplit(".", 1)[1], schema=schema, partial=True
                )
        elif t.get_origin(type_) in (list, tuple, set):
            return cls.from_type(t.get_args(type_)[0])
        else:
            schema = type_

        if not schemas.adapter.is_schema(schema):
            raise ValueError("Wrong schema type")

        return cls(schema=schema)

    @classmethod
    def build(
        cls,
        name: t.Optional[str] = None,
        schema: t.Any = None,
        fields: t.Optional[list[Field]] = None,
    ) -> "Schema":
        return cls(
            schema=schemas.adapter.build_schema(
                name=name, schema=schema, fields={f.name: f.field for f in (fields or [])}
            ),
        )

    @classmethod
    def is_schema(cls, obj: t.Any) -> bool:
        return schemas.adapter.is_schema(obj)

    @property
    def name(self) -> str:
        return schemas.adapter.name(self.schema)

    def _fix_ref(self, value: str, refs: dict[str, str]) -> str:
        try:
            prefix, name = value.rsplit("/", 1)
            return f"{prefix}/{refs[name]}"
        except KeyError:
            return value

    def _replace_json_schema_refs(self, schema: types.JSONField, refs: dict[str, str]) -> types.JSONField:
        if isinstance(schema, dict):
            return {
                k: self._fix_ref(t.cast(str, v), refs) if k == "$ref" else self._replace_json_schema_refs(v, refs)
                for k, v in schema.items()
            }

        if isinstance(schema, (list, tuple, set)):
            return [self._replace_json_schema_refs(x, refs) for x in schema]

        return schema

    def json_schema(self, names: dict[int, str]) -> types.JSONSchema:
        return t.cast(
            types.JSONSchema,
            self._replace_json_schema_refs(
                schemas.adapter.to_json_schema(self.schema),
                {Schema(x).name.rsplit(".", 1)[1]: names[id(Schema(x).unique_schema)] for x in self.nested_schemas()},
            ),
        )

    @property
    def unique_schema(self) -> t.Any:
        return schemas.adapter.unique_schema(self.schema)

    @property
    def fields(self) -> dict[str, tuple[t.Any, t.Any]]:
        return schemas.adapter.schema_fields(self.unique_schema)

    def nested_schemas(self, schema: t.Any = UNKNOWN) -> list[t.Any]:
        if schema == UNKNOWN:
            return self.nested_schemas(self)

        if schemas.adapter.is_schema(schema):
            return [schemas.adapter.unique_schema(schema)]

        if t.get_origin(schema) in (t.Union, compat.UnionType):
            return [x for field in t.get_args(schema) for x in self.nested_schemas(field)]

        if isinstance(schema, (list, tuple, set)):
            return [x for field in schema for x in self.nested_schemas(field)]

        if isinstance(schema, dict):
            return [x for field in schema.values() for x in self.nested_schemas(field)]

        if isinstance(schema, Schema):
            return [x for field_type, _ in schema.fields.values() for x in self.nested_schemas(field_type)]

        return []

    @t.overload
    def validate(self, values: None, *, partial: bool = False) -> dict[str, t.Any]:
        ...

    @t.overload
    def validate(self, values: dict[str, t.Any], *, partial: bool = False) -> dict[str, t.Any]:
        ...

    @t.overload
    def validate(self, values: list[dict[str, t.Any]], *, partial: bool = False) -> list[dict[str, t.Any]]:
        ...

    def validate(self, values: t.Union[dict[str, t.Any], list[dict[str, t.Any]], None], *, partial=False):
        if isinstance(values, (list, tuple)):
            return [schemas.adapter.validate(self.schema, value, partial=partial) for value in values]

        return schemas.adapter.validate(self.schema, values or {}, partial=partial)

    @t.overload
    def load(self, values: dict[str, t.Any]) -> t.Any:
        ...

    @t.overload
    def load(self, values: list[dict[str, t.Any]]) -> list[t.Any]:
        ...

    def load(self, values):
        if isinstance(values, (list, tuple)):
            return [schemas.adapter.load(self.schema, value) for value in values]

        return schemas.adapter.load(self.schema, values)

    @t.overload
    def dump(self, values: dict[str, t.Any]) -> dict[str, t.Any]:
        ...

    @t.overload
    def dump(self, values: list[dict[str, t.Any]]) -> list[dict[str, t.Any]]:
        ...

    def dump(self, values):
        if isinstance(values, (list, tuple)):
            return [schemas.adapter.dump(self.schema, value) for value in values]

        return schemas.adapter.dump(self.schema, values)


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    location: ParameterLocation
    type: t.Any
    required: bool = True
    default: t.Any = InjectionParameter.empty
    nullable: bool = dataclasses.field(init=False)
    multiple: bool = dataclasses.field(init=False)
    schema: "Schema" = dataclasses.field(hash=False, init=False, compare=False)
    field: "Field" = dataclasses.field(hash=False, init=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "nullable", type(None) in t.get_args(self.type) or self.default is None)

        try:
            schema = Schema.from_type(self.type)
            field = None
        except ValueError:
            if self.type in (None, InjectionParameter.empty):
                schema = Schema(schema=None)
                field = None
            else:
                schema = None
                field = Field(self.name, self.type, required=self.required, default=self.default)

        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "field", field)
        object.__setattr__(self, "multiple", t.get_origin(self.type) in (list, tuple, set, frozenset))

    @classmethod
    def build(cls, type_: str, parameter: InjectionParameter):
        return {
            "path": cls._build_path_parameter,
            "query": cls._build_query_parameter,
            "body": cls._build_body_parameter,
            "response": cls._build_response_parameter,
        }[type_](parameter)

    @classmethod
    def _build_path_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(
            name=parameter.name,
            location=ParameterLocation.path,
            type=parameter.annotation if parameter.annotation is not parameter.empty else str,
        )

    @classmethod
    def _build_query_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(
            name=parameter.name,
            location=ParameterLocation.query,
            type=parameter.annotation if parameter.annotation is not parameter.empty else str,
            required=parameter.default is InjectionParameter.empty,
            default=parameter.default,
        )

    @classmethod
    def _build_body_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(name=parameter.name, location=ParameterLocation.body, type=parameter.annotation)

    @classmethod
    def _build_response_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(name=parameter.name, location=ParameterLocation.response, type=parameter.annotation)


Parameters = dict[str, Parameter]
