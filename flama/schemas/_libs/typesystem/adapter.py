import inspect
import typing as t

import typesystem

from flama.schemas._libs.typesystem.fields import MAPPING
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError

__all__ = ["TypesystemAdapter"]


class TypesystemAdapter(Adapter[typesystem.Schema, typesystem.Field]):
    def build_field(self, field_type: t.Type, required: bool, default: t.Any, **kwargs) -> typesystem.Field:
        if required is False:
            kwargs["default"] = default
            if default is None:
                kwargs["allow_null"] = True

        return MAPPING[field_type](**kwargs)

    def build_schema(
        self,
        schema: t.Optional[t.Union[typesystem.Schema, t.Type[typesystem.Schema]]] = None,
        pagination: t.Optional[t.Union[typesystem.Schema, t.Type[typesystem.Schema]]] = None,
        paginated_schema_name: t.Optional[str] = None,
        name: str = "Schema",
        fields: t.Optional[t.Dict[str, typesystem.Field]] = None,
    ) -> typesystem.Schema:
        if fields is None:
            fields = {}

        if inspect.isclass(schema):
            schema = schema()

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

    def validate(self, schema: t.Union[typesystem.Schema, typesystem.Field], values: t.Dict[str, t.Any]) -> t.Any:
        try:
            return schema.validate(values)
        except typesystem.ValidationError as errors:
            raise SchemaValidationError(errors={k: [v] for k, v in errors.items()})

    def load(self, schema: typesystem.Schema, value: t.Dict[str, t.Any]) -> t.Any:
        return schema.validate(value)

    def dump(
        self,
        schema: t.Union[typesystem.Field, typesystem.Schema],
        value: t.Dict[str, t.Any],
    ) -> t.Any:
        return self._dump(self.validate(schema, value))

    def _dump(self, value: t.Dict[str, t.Any]) -> t.Any:
        if isinstance(value, typesystem.Schema):
            return dict(value)

        if isinstance(value, list):
            return [self._dump(x) for x in value]

        return value

    def to_json_schema(self, schema: t.Union[typesystem.Schema, typesystem.Field]) -> t.Dict[str, t.Any]:
        try:
            json_schema = typesystem.to_json_schema(schema)

            if not isinstance(json_schema, dict):
                raise SchemaGenerationError

            json_schema.pop("components", None)
        except Exception as e:
            raise SchemaGenerationError from e

        return json_schema

    def unique_schema(self, schema: t.Union[typesystem.Schema, typesystem.Array]) -> typesystem.Schema:
        if isinstance(schema, typesystem.Array):
            if not isinstance(schema.items, typesystem.Reference):
                raise ValueError("Schema cannot be resolved")

            item_schema: typesystem.Schema = schema.items.target
            return item_schema

        return schema

    def is_schema(self, obj: t.Union[typesystem.Schema, t.Type[typesystem.Schema]]) -> bool:
        return isinstance(obj, typesystem.Schema) or (inspect.isclass(obj) and issubclass(obj, typesystem.Schema))

    def is_field(self, obj: t.Union[typesystem.Field, t.Type[typesystem.Field]]) -> bool:
        return isinstance(obj, typesystem.Field) or (inspect.isclass(obj) and issubclass(obj, typesystem.Field))
