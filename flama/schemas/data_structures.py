import dataclasses
import enum
import sys
import typing as t

from flama import schemas, types
from flama.injection.resolver import Parameter as InjectionParameter

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard  # type: ignore

__all__ = ["Field", "Schema", "Parameter", "Parameters"]


UNKNOWN = t.TypeVar("UNKNOWN")


class ParameterLocation(enum.Enum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()
    response = enum.auto()


@dataclasses.dataclass(frozen=True)
class Field:
    name: str
    type: t.Type
    nullable: bool = dataclasses.field(init=False)
    field: t.Any = dataclasses.field(hash=False, init=False, compare=False)
    multiple: t.Optional[bool] = dataclasses.field(hash=False, compare=False, default=None)
    required: bool = True
    default: t.Any = InjectionParameter.empty

    def __post_init__(self) -> None:
        object.__setattr__(self, "nullable", type(None) in t.get_args(self.type) or self.default is None)

        field_type = t.get_args(self.type)[0] if t.get_origin(self.type) in (list, t.Union) else self.type

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
            parameter.type,
            required=parameter.default is InjectionParameter.empty,
            default=parameter.default
            if parameter.default is not InjectionParameter.empty
            else InjectionParameter.empty,
        )

    @classmethod
    def is_field(cls, obj: t.Any) -> bool:
        return schemas.adapter.is_field(obj)

    @classmethod
    def is_http_valid_type(cls, type_: t.Type) -> bool:
        origin = t.get_origin(type_)
        args = t.get_args(type_)
        NoneType = type(None)

        return (
            (type_ in types.PARAMETERS_TYPES)
            or (origin is t.Union and len(args) == 2 and args[0] in types.PARAMETERS_TYPES and args[1] is NoneType)
            or (origin is list and args[0] in types.PARAMETERS_TYPES)
        )

    @property
    def json_schema(self) -> types.JSONSchema:
        return schemas.adapter.to_json_schema(self.field)


@dataclasses.dataclass(frozen=True)
class Schema:
    schema: t.Any = dataclasses.field(hash=False, compare=False)

    @classmethod
    def from_type(cls, type_: t.Optional[t.Type]) -> "Schema":
        if types.is_schema(type_):
            schema = type_.schema
        elif t.get_origin(type_) in (list, tuple, set):
            schema = t.get_args(type_)[0]
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
        fields: t.Optional[t.List[Field]] = None,
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

    @property
    def json_schema(self) -> types.JSONSchema:
        return schemas.adapter.to_json_schema(self.schema)

    @property
    def unique_schema(self) -> t.Any:
        return schemas.adapter.unique_schema(self.schema)

    @property
    def fields(self) -> t.Dict[str, t.Tuple[t.Any, t.Any]]:
        return schemas.adapter.schema_fields(self.unique_schema)

    def nested_schemas(self, schema: t.Any = UNKNOWN) -> t.List[t.Any]:
        if schema == UNKNOWN:
            return self.nested_schemas(self)

        if schemas.adapter.is_schema(schema):
            return [schema]

        if isinstance(schema, (list, tuple, set)):
            return [x for field in schema for x in self.nested_schemas(field)]

        if isinstance(schema, dict):
            return [x for field in schema.values() for x in self.nested_schemas(field)]

        if isinstance(schema, Schema):
            return [x for field_type, _ in schema.fields.values() for x in self.nested_schemas(field_type)]

        return []

    @t.overload
    def validate(self, values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @t.overload
    def validate(self, values: t.List[t.Dict[str, t.Any]]) -> t.List[t.Dict[str, t.Any]]:
        ...

    def validate(self, values):
        if isinstance(values, (list, tuple)):
            return [schemas.adapter.validate(self.schema, value) for value in values]

        return schemas.adapter.validate(self.schema, values)

    @t.overload
    def load(self, values: t.Dict[str, t.Any]) -> t.Any:
        ...

    @t.overload
    def load(self, values: t.List[t.Dict[str, t.Any]]) -> t.List[t.Any]:
        ...

    def load(self, values):
        if isinstance(values, (list, tuple)):
            return [schemas.adapter.load(self.schema, value) for value in values]

        return schemas.adapter.load(self.schema, values)

    @t.overload
    def dump(self, values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @t.overload
    def dump(self, values: t.List[t.Dict[str, t.Any]]) -> t.List[t.Dict[str, t.Any]]:
        ...

    def dump(self, values):
        if isinstance(values, (list, tuple)):
            return [schemas.adapter.dump(self.schema, value) for value in values]

        return schemas.adapter.dump(self.schema, values)


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    location: ParameterLocation
    type: t.Type
    required: bool = True
    default: t.Any = InjectionParameter.empty
    nullable: bool = dataclasses.field(init=False)
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
            type=parameter.type if parameter.type is not parameter.empty else str,
            location=ParameterLocation.path,
        )

    @classmethod
    def _build_query_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(
            name=parameter.name,
            type=parameter.type if parameter.type is not parameter.empty else str,
            location=ParameterLocation.query,
            required=parameter.default is InjectionParameter.empty,
            default=parameter.default,
        )

    @classmethod
    def _build_body_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(name=parameter.name, type=parameter.type, location=ParameterLocation.body)

    @classmethod
    def _build_response_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(name=parameter.name, type=parameter.type, location=ParameterLocation.response)


Parameters = t.Dict[str, Parameter]
