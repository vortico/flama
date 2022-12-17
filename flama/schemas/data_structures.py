import dataclasses
import sys
import typing as t

from flama import schemas, types
from flama.injection.resolver import Parameter as InjectionParameter
from flama.schemas.types import ParameterLocation

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard
else:  # pragma: no cover
    from typing_extensions import TypeGuard

__all__ = ["Field", "Schema", "Parameter", "Parameters"]


@dataclasses.dataclass(frozen=True)
class Field:
    name: str
    type: t.Type
    nullable: bool = dataclasses.field(init=False)
    field: t.Any = dataclasses.field(hash=False, init=False, compare=False)
    multiple: bool = dataclasses.field(hash=False, init=False, compare=False)
    required: bool = True
    default: t.Any = InjectionParameter.empty

    def __post_init__(self) -> None:
        object.__setattr__(self, "nullable", type(None) in t.get_args(self.type) or self.default is None)
        object.__setattr__(self, "multiple", t.get_origin(self.type) is list)
        object.__setattr__(
            self,
            "field",
            schemas.adapter.build_field(
                self.name,
                t.get_args(self.type)[0] if t.get_origin(self.type) in (list, t.Union) else self.type,
                nullable=self.nullable,
                required=self.required,
                default=self.default,
                multiple=self.multiple,
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
    def json_schema(self) -> schemas.types.JSONSchema:
        schema = schemas.adapter.to_json_schema(self.field)

        if self.multiple:
            schema = {"items": {"$ref": schema}, "type": "array"}

        return schema


@dataclasses.dataclass(frozen=True)
class Schema:
    schema: t.Any = dataclasses.field(hash=False, compare=False)
    multiple: bool = dataclasses.field(hash=False, compare=False, default=False)

    @classmethod
    def from_type(cls, type: t.Optional[t.Type]) -> "Schema":
        multiple = t.get_origin(type) is list
        schema = t.get_args(type)[0] if multiple else type

        if not schemas.adapter.is_schema(schema):
            raise ValueError("Wrong schema type")

        return cls(schema=schema, multiple=multiple)

    @classmethod
    def build(
        cls,
        name: t.Optional[str] = None,
        schema: t.Any = None,
        fields: t.Optional[t.List[Field]] = None,
        multiple: bool = False,
    ) -> "Schema":
        return cls(
            schema=schemas.adapter.build_schema(
                name=name, schema=schema, fields={f.name: f.field for f in (fields or [])}
            ),
            multiple=multiple,
        )

    @classmethod
    def is_schema(cls, obj: t.Any) -> bool:
        return schemas.adapter.is_schema(obj)

    @property
    def json_schema(self) -> t.Dict[str, t.Any]:
        schema = schemas.adapter.to_json_schema(self.schema)

        if self.multiple:
            schema = {"items": {"$ref": schema}, "type": "array"}

        return schema

    @property
    def unique_schema(self) -> t.Any:
        return schemas.adapter.unique_schema(self.schema)

    @t.overload
    def validate(self, values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @t.overload
    def validate(self, values: t.List[t.Dict[str, t.Any]]) -> t.List[t.Dict[str, t.Any]]:
        ...

    def validate(self, values):
        if self.multiple and isinstance(values, (list, tuple)):
            return [schemas.adapter.validate(self.schema, value) for value in values]

        return schemas.adapter.validate(self.schema, values)

    @t.overload
    def load(self, values: t.Dict[str, t.Any]) -> t.Any:
        ...

    @t.overload
    def load(self, values: t.List[t.Dict[str, t.Any]]) -> t.List[t.Any]:
        ...

    def load(self, values):
        if self.multiple:
            return [schemas.adapter.load(self.schema, value) for value in values]

        return schemas.adapter.load(self.schema, values)

    @t.overload
    def dump(self, values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @t.overload
    def dump(self, values: t.List[t.Dict[str, t.Any]]) -> t.List[t.Dict[str, t.Any]]:
        ...

    def dump(self, values):
        if self.multiple and isinstance(values, (list, tuple)):
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
    schema: Schema = dataclasses.field(hash=False, init=False, compare=False)
    field: Field = dataclasses.field(hash=False, init=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "nullable", type(None) in t.get_args(self.type) or self.default is None)

        try:
            schema = Schema.from_type(self.type)
            field = None
        except ValueError:
            if self.type in (None, InjectionParameter.empty):
                schema = Schema(schema=None, multiple=False)
                field = None
            else:
                schema = None
                field = Field(self.name, self.type, required=self.required, default=self.default)

        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "field", field)

    @property
    def is_field(self) -> TypeGuard[Field]:
        return isinstance(self.schema, Field)

    @property
    def is_schema(self) -> TypeGuard[Schema]:
        return isinstance(self.schema, Schema)

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
