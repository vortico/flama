import enum
import inspect
import typing

from flama import schemas

__all__ = ["ParameterLocation", "Parameter", "Parameters", "Methods", "EndpointInfo", "SchemaInfo", "Schemas", "Schema"]


Field = typing.TypeVar("Field")
Schema = typing.TypeVar("Schema")
Schemas = typing.NewType("Schemas", typing.Dict[str, Schema])


class ParameterLocation(enum.Enum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()
    output = enum.auto()


class Parameter(typing.NamedTuple):
    name: str
    location: ParameterLocation
    schema_type: typing.Union[type, Field, Schema]
    required: bool = False
    default: typing.Any = None

    @property
    def schema(self):
        if self.schema_type is None:
            return None

        if inspect.isclass(self.schema_type) and issubclass(self.schema_type, schemas.Schema):
            return self.schema_type()

        if isinstance(self.schema_type, schemas.Schema) or isinstance(self.schema_type, schemas.Field):
            return self.schema_type

        return schemas.adapter.build_field(field_type=self.schema_type, required=self.required, default=self.default)


Parameters = typing.Dict[str, Parameter]
Methods = typing.Dict[str, Parameters]


class EndpointInfo(typing.NamedTuple):
    path: str
    method: str
    func: typing.Callable
    query_parameters: typing.Dict[str, Parameter]
    path_parameters: typing.Dict[str, Parameter]
    body_parameter: Parameter
    output_parameter: Parameter


class SchemaInfo(typing.NamedTuple):
    name: str
    schema: typing.Dict

    @property
    def ref(self) -> str:
        return f"#/components/schemas/{self.name}"

    @property
    def json_schema(self) -> typing.Dict[str, typing.Any]:
        return schemas.adapter.to_json_schema(self.schema)
