import abc
import typing

Field = typing.TypeVar("Field")
Schema = typing.TypeVar("Schema")


class Adapter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def build_field(self, field_type: typing.Type, required: bool, default: typing.Any) -> Field:
        ...

    @abc.abstractmethod
    def build_schema(
        self,
        schema: Schema = None,
        pagination: Schema = None,
        paginated_schema_name: str = None,
        name: str = "Schema",
        fields: typing.Dict[str, Field] = None,
    ) -> Schema:
        ...

    @abc.abstractmethod
    def validate(self, schema: Schema, values: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        ...

    @abc.abstractmethod
    def load(self, schema: Schema, value: typing.Dict[str, typing.Any]) -> Schema:
        ...

    @abc.abstractmethod
    def dump(self, schema: Schema, value: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        ...

    @abc.abstractmethod
    def to_json_schema(self, schema: typing.Union[Schema, Field]) -> typing.Dict[str, typing.Any]:
        ...

    @abc.abstractmethod
    def unique_instance(self, schema: Schema) -> Schema:
        ...
