import enum
import inspect
import typing

from flama import schemas

__all__ = ["FieldLocation", "Field", "Fields", "Methods", "EndpointInfo", "SchemaInfo", "Schemas"]


Schemas = typing.NewType("Schemas", typing.Dict[str, schemas.Schema])


class FieldLocation(enum.Enum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()
    output = enum.auto()


class Field(typing.NamedTuple):
    name: str
    location: FieldLocation
    schema_type: typing.Union[type, schemas.Schema, schemas.Field]
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

        return schemas.build_field(field_type=self.schema_type, required=self.required, default=self.default)


Fields = typing.Dict[str, Field]
Methods = typing.Dict[str, Fields]


class EndpointInfo(typing.NamedTuple):
    path: str
    method: str
    func: typing.Callable
    query_fields: typing.Dict[str, Field]
    path_fields: typing.Dict[str, Field]
    body_field: Field
    output_field: Field


class SchemaInfo(typing.NamedTuple):
    name: str
    schema: typing.Dict

    @property
    def ref(self) -> str:
        return f"#/components/schemas/{self.name}"

    @property
    def json_schema(self) -> typing.Dict[str, typing.Any]:
        return schemas.to_json_schema(self.schema)
