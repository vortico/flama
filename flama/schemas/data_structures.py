import dataclasses
import sys
import typing as t

from flama import schemas
from flama.injection.resolver import Parameter as InjectionParameter
from flama.schemas.types import ParameterLocation
from flama.types import FIELDS_TYPE_MAPPING, OPTIONAL_FIELD_TYPE_MAPPING

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    pass
else:  # pragma: no cover
    pass

__all__ = ["Schema", "Parameter", "Parameters"]


@dataclasses.dataclass(frozen=True)
class Schema:
    schema: t.Union[schemas.Schema, t.Type[schemas.Schema]] = dataclasses.field(hash=False, compare=False)
    multiple: bool = dataclasses.field(hash=False, compare=False, default=False)

    @classmethod
    def from_type(cls, type: t.Optional[t.Type]) -> "Schema":
        multiple = t.get_origin(type) in (list, tuple)
        schema = t.get_args(type)[0] if multiple else type

        if not schemas.adapter.is_schema(schema):
            raise ValueError("Wrong schema type")

        return cls(schema=schema, multiple=multiple)

    @classmethod
    def from_fields(cls, fields: t.Dict[str, schemas.Field]) -> "Schema":
        return cls(schema=schemas.adapter.build_schema(fields=fields))

    @property
    def json_schema(self) -> t.Dict[str, t.Any]:
        schema = schemas.adapter.to_json_schema(self.schema)

        if self.multiple:
            schema = {"items": {"$ref": schema}, "type": "array"}

        return schema

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
    def load(self, values: t.Dict[str, t.Any]) -> schemas.Schema:
        ...

    @t.overload
    def load(self, values: t.List[t.Dict[str, t.Any]]) -> t.List[schemas.Schema]:
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

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "nullable",
            self.type in OPTIONAL_FIELD_TYPE_MAPPING or type(None) in t.get_args(self.type) or self.default is None,
        )

        try:
            schema = Schema.from_type(self.type)
        except ValueError:
            if self.type in (None, InjectionParameter.empty):
                schema = Schema(schema=None, multiple=False)
            else:
                schema = Schema(
                    schema=schemas.adapter.build_field(
                        name=self.name,
                        type=FIELDS_TYPE_MAPPING.get(self.type, str),
                        required=self.required,
                        default=self.default,
                        nullable=self.nullable,
                    ),
                    multiple=False,
                )

        object.__setattr__(self, "schema", schema)

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
        return cls(name=parameter.name, type=parameter.type, location=ParameterLocation.path)

    @classmethod
    def _build_query_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(
            name=parameter.name,
            type=parameter.type,
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
