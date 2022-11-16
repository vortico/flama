import dataclasses
import inspect
import typing as t

from flama import schemas
from flama.injection.resolver import Parameter as InjectionParameter
from flama.schemas.types import ParameterLocation
from flama.types import FIELDS_TYPE_MAPPING, OPTIONAL_FIELD_TYPE_MAPPING

__all__ = ["Parameter", "Parameters"]


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    location: ParameterLocation
    schema_type: t.Optional[t.Union[t.Type[schemas.Field], t.Type[schemas.Schema], schemas.Field, schemas.Schema]]
    required: bool = False
    default: t.Any = None

    @property
    def schema(self) -> t.Optional[t.Union[schemas.Field, schemas.Schema]]:
        if self.schema_type is None:
            return None

        if inspect.isclass(self.schema_type) and issubclass(self.schema_type, schemas.Schema):
            return self.schema_type()

        if isinstance(self.schema_type, schemas.Schema) or isinstance(self.schema_type, schemas.Field):
            return self.schema_type

        return schemas.adapter.build_field(field_type=self.schema_type, required=self.required, default=self.default)

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
            schema_type=FIELDS_TYPE_MAPPING.get(parameter.type, str),
            required=True,
        )

    @classmethod
    def _build_query_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        if parameter.type in OPTIONAL_FIELD_TYPE_MAPPING or parameter.default is not parameter.empty:
            required = False
            default = parameter.default if parameter.default is not parameter.empty else None
        else:
            required = True
            default = None

        return cls(
            name=parameter.name,
            location=ParameterLocation.query,
            schema_type=FIELDS_TYPE_MAPPING[parameter.type],
            required=required,
            default=default,
        )

    @classmethod
    def _build_body_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(name=parameter.name, location=ParameterLocation.body, schema_type=parameter.type)

    @classmethod
    def _build_response_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(
            name=parameter.name,
            location=ParameterLocation.response,
            schema_type=parameter.type if parameter.type is not InjectionParameter.empty else None,
        )


Parameters = t.Dict[str, Parameter]
