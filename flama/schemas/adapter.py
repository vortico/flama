import abc
import typing

from flama.schemas.types import Field, Schema


class Adapter(typing.Generic[Schema, Field], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def build_field(self, field_type: typing.Type, required: bool, default: typing.Any) -> Field:
        ...

    @abc.abstractmethod
    def build_schema(
        self,
        schema: typing.Optional[Schema] = None,
        pagination: typing.Optional[Schema] = None,
        paginated_schema_name: typing.Optional[str] = None,
        name: str = "Schema",
        fields: typing.Optional[typing.Dict[str, Field]] = None,
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
    def unique_schema(self, schema: Schema) -> Schema:
        ...

    @abc.abstractmethod
    def is_schema(self, obj: typing.Union[Schema, typing.Type[Schema]]) -> bool:
        ...

    @abc.abstractmethod
    def is_field(self, obj: typing.Union[Field, typing.Type[Field]]) -> bool:
        ...
