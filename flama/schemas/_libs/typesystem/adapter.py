import inspect
import sys
import typing as t

import typesystem

from flama.injection import Parameter
from flama.schemas._libs.typesystem.fields import MAPPING
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard
else:  # pragma: no cover
    from typing_extensions import TypeGuard

__all__ = ["TypesystemAdapter"]

Schema = typesystem.Schema
Field = typesystem.Field


class TypesystemAdapter(Adapter[Schema, Field]):
    def build_field(
        self,
        name: str,
        type: t.Type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        **kwargs: t.Any
    ) -> Field:
        if required is False and default is not Parameter.empty:
            kwargs["default"] = default

        return MAPPING[type](**{**kwargs, "allow_null": nullable, "title": name})

    def build_schema(
        self,
        name: str = "Schema",
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        pagination: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        paginated_schema_name: t.Optional[str] = None,
        fields: t.Optional[t.Dict[str, Field]] = None,
    ) -> Schema:
        if fields is None:
            fields = {}

        if inspect.isclass(schema):
            schema = schema()

        if schema:
            fields.update(schema.fields)

        if pagination:
            base_schema = Schema(fields=fields)
            definitions = typesystem.Definitions()
            definitions[name] = base_schema
            data_schema = typesystem.Reference(to=name, definitions=definitions) if schema else typesystem.Object()
            fields = {
                **pagination.fields,
                **{"data": typesystem.Array(data_schema)},
            }

        return Schema(fields=fields)

    def validate(self, schema: t.Union[Schema, Field], values: t.Dict[str, t.Any]) -> t.Any:
        try:
            return schema.validate(values)
        except typesystem.ValidationError as errors:
            raise SchemaValidationError(errors={k: [v] for k, v in errors.items()})

    def load(self, schema: Schema, value: t.Dict[str, t.Any]) -> t.Any:
        return schema.validate(value)

    def dump(self, schema: t.Union[Field, Schema], value: t.Dict[str, t.Any]) -> t.Any:
        return self._dump(self.validate(schema, value))

    def _dump(self, value: t.Any) -> t.Any:
        if isinstance(value, Schema):
            return dict(value)

        if isinstance(value, list):
            return [self._dump(x) for x in value]

        return value

    def to_json_schema(self, schema: t.Union[Schema, Field]) -> t.Dict[str, t.Any]:
        try:
            json_schema = typesystem.to_json_schema(schema)

            if not isinstance(json_schema, dict):
                raise SchemaGenerationError

            json_schema.pop("components", None)
        except Exception as e:
            raise SchemaGenerationError from e

        return json_schema

    def unique_schema(self, schema: t.Union[Schema, typesystem.Array]) -> Schema:
        if isinstance(schema, typesystem.Array):
            if not isinstance(schema.items, typesystem.Reference):
                raise ValueError("Schema cannot be resolved")

            item_schema: Schema = schema.items.target
            return item_schema

        return schema

    def is_schema(self, obj: t.Any) -> TypeGuard[t.Union[Schema, t.Type[Schema]]]:
        return isinstance(obj, Schema) or (inspect.isclass(obj) and issubclass(obj, Schema))

    def is_field(self, obj: t.Any) -> TypeGuard[t.Union[Field, t.Type[Field]]]:
        return isinstance(obj, Field) or (inspect.isclass(obj) and issubclass(obj, Field))
