import inspect
import sys
import typing as t

import marshmallow
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin, resolve_schema_cls

from flama.injection import Parameter
from flama.schemas._libs.marshmallow.fields import MAPPING, MAPPING_TYPES
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError
from flama.types import JSONSchema

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard  # type: ignore

if t.TYPE_CHECKING:
    from apispec.ext.marshmallow import OpenAPIConverter

__all__ = ["MarshmallowAdapter"]

Schema = marshmallow.Schema
Field = marshmallow.fields.Field


class MarshmallowAdapter(Adapter[Schema, Field]):
    def build_field(
        self,
        name: str,
        type_: t.Type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        multiple: bool = False,
        **kwargs,
    ) -> Field:
        field_args = {
            "required": required,
            "allow_none": nullable,
            "metadata": {**kwargs, "title": name},
        }

        if not required:
            field_args["load_default"] = default if default is not Parameter.empty else None

        if multiple:
            return marshmallow.fields.List(
                marshmallow.fields.Nested(type_) if self.is_schema(type_) else MAPPING[type_](),
                **field_args,
            )

        return MAPPING[type_](**field_args)

    def build_schema(
        self,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        fields: t.Optional[t.Dict[str, Field]] = None,
    ) -> t.Type[Schema]:
        return Schema.from_dict(
            fields={**(self.unique_schema(schema)().fields if schema else {}), **(fields or {})},
            name=name or self.DEFAULT_SCHEMA_NAME,
        )

    def validate(self, schema: t.Union[t.Type[Schema], Schema], values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        try:
            return t.cast(t.Dict[str, t.Any], self._schema_instance(schema).load(values, unknown=marshmallow.EXCLUDE))
        except marshmallow.ValidationError as exc:
            raise SchemaValidationError(errors=exc.normalized_messages())

    def load(self, schema: t.Union[t.Type[Schema], Schema], value: t.Dict[str, t.Any]) -> Schema:
        return t.cast(Schema, self._schema_instance(schema).load(value))

    def dump(self, schema: t.Union[t.Type[Schema], Schema], value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        try:
            return t.cast(t.Dict[str, t.Any], self._schema_instance(schema).dump(value))
        except Exception as exc:
            raise SchemaValidationError(errors=str(exc))

    def name(self, schema: t.Union[Schema, t.Type[Schema]]) -> str:
        s = self.unique_schema(schema)
        return s.__qualname__ if s.__module__ == "builtins" else f"{s.__module__}.{s.__qualname__}"

    def to_json_schema(self, schema: t.Union[t.Type[Schema], t.Type[Field], Schema, Field]) -> JSONSchema:
        json_schema: t.Dict[str, t.Any]
        try:
            plugin = MarshmallowPlugin(schema_name_resolver=lambda x: resolve_schema_cls(x).__name__)
            APISpec("", "", "3.1.0", [plugin])
            converter: "OpenAPIConverter" = t.cast("OpenAPIConverter", plugin.converter)

            if (inspect.isclass(schema) and issubclass(schema, Field)) or isinstance(schema, Field):
                json_schema = converter.field2property(t.cast(marshmallow.fields.Field, schema))
            elif inspect.isclass(schema) and issubclass(schema, Schema):
                json_schema = converter.schema2jsonschema(schema)
            elif isinstance(schema, Schema):
                if getattr(schema, "many", False):
                    json_schema = {
                        "type": "array",
                        "items": converter.schema2jsonschema(schema),
                        "additionalItems": False,
                    }
                else:
                    json_schema = converter.schema2jsonschema(schema)
            else:
                raise SchemaGenerationError
        except Exception as e:
            raise SchemaGenerationError from e

        return json_schema

    def unique_schema(self, schema: t.Union[Schema, t.Type[Schema]]) -> t.Type[Schema]:
        if isinstance(schema, Schema):
            return schema.__class__

        return schema

    def _get_field_type(self, field: Field) -> t.Union[Schema, t.Type]:
        if isinstance(field, marshmallow.fields.Nested):
            return field.schema

        if isinstance(field, marshmallow.fields.List):
            return self._get_field_type(t.cast(marshmallow.fields.Field, field.inner))

        if isinstance(field, marshmallow.fields.Dict):
            return self._get_field_type(t.cast(marshmallow.fields.Field, field.value_field))

        try:
            return MAPPING_TYPES[field.__class__]
        except KeyError:
            return None

    def schema_fields(
        self, schema: t.Union[Schema, t.Type[Schema]]
    ) -> t.Dict[str, t.Tuple[t.Union[t.Type, Schema], Field]]:
        return {
            name: (self._get_field_type(field), field) for name, field in self._schema_instance(schema).fields.items()
        }

    def is_schema(self, obj: t.Any) -> t.TypeGuard[t.Union[Schema, t.Type[Schema]]]:  # type: ignore
        return isinstance(obj, Schema) or (inspect.isclass(obj) and issubclass(obj, Schema))

    def is_field(self, obj: t.Any) -> t.TypeGuard[t.Union[Field, t.Type[Field]]]:  # type: ignore
        return isinstance(obj, Field) or (inspect.isclass(obj) and issubclass(obj, Field))

    def _schema_instance(self, schema: t.Union[t.Type[Schema], Schema]) -> Schema:
        if inspect.isclass(schema) and issubclass(schema, Schema):
            return schema()
        elif isinstance(schema, Schema):
            return schema
        else:
            raise ValueError("Wrong schema")
