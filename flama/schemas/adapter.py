import abc
import typing as t

from flama.schemas.types import Field, Schema


class Adapter(t.Generic[Schema, Field], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def build_field(self, field_type: t.Type, required: bool, default: t.Any) -> Field:
        ...

    @abc.abstractmethod
    def build_schema(
        self,
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        pagination: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        paginated_schema_name: t.Optional[str] = None,
        name: str = "Schema",
        fields: t.Optional[t.Dict[str, Field]] = None,
    ) -> t.Union[Schema, t.Type[Schema]]:
        ...

    @abc.abstractmethod
    def validate(self, schema: Schema, values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def load(self, schema: Schema, value: t.Dict[str, t.Any]) -> Schema:
        ...

    @abc.abstractmethod
    def dump(self, schema: Schema, value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def to_json_schema(self, schema: t.Union[Schema, Field]) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def unique_schema(self, schema: Schema) -> t.Union[Schema, t.Type[Schema]]:
        ...

    @abc.abstractmethod
    def is_schema(self, obj: t.Union[Schema, t.Type[Schema]]) -> bool:
        ...

    @abc.abstractmethod
    def is_field(self, obj: t.Union[Field, t.Type[Field]]) -> bool:
        ...
