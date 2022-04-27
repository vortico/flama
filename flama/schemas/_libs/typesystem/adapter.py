import inspect
import typing

import typesystem

from flama.schemas._libs.typesystem.fields import MAPPING
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError

__all__ = ["TypesystemAdapter"]


class TypesystemAdapter(Adapter[typesystem.Schema, typesystem.Field]):
    def build_field(self, field_type: typing.Type, required: bool, default: typing.Any, **kwargs) -> typesystem.Field:
        if required is False and default is None:
            kwargs["allow_null"] = True
        else:
            kwargs["default"] = default

        return MAPPING[field_type](**kwargs)

    def build_schema(
        self,
        schema: typing.Optional[typesystem.Schema] = None,
        pagination: typing.Optional[typesystem.Schema] = None,
        paginated_schema_name: typing.Optional[str] = None,
        name: str = "Schema",
        fields: typing.Optional[typing.Dict[str, typesystem.Field]] = None,
    ) -> typesystem.Schema:
        if fields is None:
            fields = {}

        if schema:
            fields.update(schema.fields)

        if pagination:
            base_schema = typesystem.Schema(fields=fields)
            definitions = typesystem.Definitions()
            definitions[name] = base_schema
            data_schema = typesystem.Reference(to=name, definitions=definitions) if schema else typesystem.Object()
            fields = {
                **pagination.fields,
                **{"data": typesystem.Array(data_schema)},
            }

        return typesystem.Schema(fields=fields)

    def validate(
        self, schema: typing.Union[typesystem.Schema, typesystem.Field], values: typing.Dict[str, typing.Any]
    ) -> typing.Any:
        try:
            return schema.validate(values)
        except typesystem.ValidationError as errors:
            raise SchemaValidationError(errors={k: [v] for k, v in errors.items()})

    def load(self, schema: typesystem.Schema, value: typing.Dict[str, typing.Any]) -> typing.Any:
        return schema.validate(value)

    def dump(
        self,
        schema: typing.Union[typesystem.Field, typesystem.Schema],
        value: typing.Dict[str, typing.Any],
    ) -> typing.Any:
        return self._dump(self.validate(schema, value))

    def _dump(self, value: typing.Dict[str, typing.Any]) -> typing.Any:
        if isinstance(value, typesystem.Schema):
            return dict(value)

        if isinstance(value, list):
            return [self._dump(x) for x in value]

        return value

    def to_json_schema(self, schema: typing.Union[typesystem.Schema, typesystem.Field]) -> typing.Dict[str, typing.Any]:
        try:
            json_schema = typesystem.to_json_schema(schema)

            if not isinstance(json_schema, dict):
                raise SchemaGenerationError

            json_schema.pop("components", None)
        except Exception as e:
            raise SchemaGenerationError from e

        return json_schema

    def unique_schema(self, schema: typing.Union[typesystem.Schema, typesystem.Array]) -> typesystem.Schema:
        if isinstance(schema, typesystem.Array):
            if not isinstance(schema.items, typesystem.Reference):
                raise ValueError("Schema cannot be resolved")

            item_schema: typesystem.Schema = schema.items.target
            return item_schema

        return schema

    def is_schema(self, obj: typing.Union[typesystem.Schema, typing.Type[typesystem.Schema]]) -> bool:
        return isinstance(obj, typesystem.Schema) or (inspect.isclass(obj) and issubclass(obj, typesystem.Schema))

    def is_field(self, obj: typing.Union[typesystem.Field, typing.Type[typesystem.Field]]) -> bool:
        return isinstance(obj, typesystem.Field) or (inspect.isclass(obj) and issubclass(obj, typesystem.Field))
