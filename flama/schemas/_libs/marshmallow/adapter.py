import inspect
import itertools
import typing as t

import marshmallow
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin, resolve_schema_cls

from flama import compat
from flama.injection import Parameter
from flama.schemas._libs.marshmallow.fields import MAPPING, MAPPING_TYPES
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError
from flama.types import JSONSchema

if t.TYPE_CHECKING:
    from apispec.ext.marshmallow import OpenAPIConverter

__all__ = ["MarshmallowAdapter"]

Schema = marshmallow.Schema
Field = marshmallow.fields.Field


class MarshmallowAdapter(Adapter[Schema, Field]):
    def build_field(
        self,
        name: str,
        type_: type,
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
        *,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Union[Schema, type[Schema]]] = None,
        fields: t.Optional[dict[str, Field]] = None,
        partial: bool = False,
    ) -> type[Schema]:
        fields_ = {**(self.unique_schema(schema)().fields if schema else {}), **(fields or {})}

        if partial:
            for field in fields_:
                fields_[field].required = False
                fields_[field].allow_none = True

        return Schema.from_dict(fields=fields_, name=name or self.DEFAULT_SCHEMA_NAME)  # type: ignore

    def validate(
        self, schema: t.Union[type[Schema], Schema], values: dict[str, t.Any], *, partial: bool = False
    ) -> dict[str, t.Any]:
        try:
            return t.cast(
                dict[str, t.Any],
                self._schema_instance(schema).load(values, unknown=marshmallow.EXCLUDE, partial=partial),
            )
        except marshmallow.ValidationError as exc:
            raise SchemaValidationError(errors=exc.normalized_messages())

    def load(self, schema: t.Union[type[Schema], Schema], value: dict[str, t.Any]) -> Schema:
        return t.cast(Schema, self._schema_instance(schema).load(value))

    def dump(self, schema: t.Union[type[Schema], Schema], value: dict[str, t.Any]) -> dict[str, t.Any]:
        try:
            dump_value = t.cast(dict[str, t.Any], self._schema_instance(schema).dump(value))
        except Exception as exc:
            raise SchemaValidationError(errors=str(exc))

        self.validate(schema, dump_value)

        return dump_value

    def name(self, schema: t.Union[Schema, type[Schema]], *, prefix: t.Optional[str] = None) -> str:
        s = self.unique_schema(schema)
        schema_name = f"{prefix or ''}{s.__qualname__}"
        return schema_name if s.__module__ == "builtins" else f"{s.__module__}.{schema_name}"

    def to_json_schema(self, schema: t.Union[type[Schema], type[Field], Schema, Field]) -> JSONSchema:
        json_schema: dict[str, t.Any]
        try:
            plugin = MarshmallowPlugin(schema_name_resolver=lambda x: t.cast(type, resolve_schema_cls(x)).__name__)
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

            for property in itertools.chain(json_schema.get("properties", {}).values(), [json_schema]):
                if isinstance(property.get("type"), list):
                    property["anyOf"] = [{"type": x} for x in property["type"]]
                    del property["type"]
        except Exception as e:
            raise SchemaGenerationError from e

        return json_schema

    def unique_schema(self, schema: t.Union[Schema, type[Schema]]) -> type[Schema]:
        if isinstance(schema, Schema):
            return schema.__class__

        return schema

    def _get_field_type(self, field: Field) -> t.Any:
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
        self, schema: t.Union[Schema, type[Schema]]
    ) -> dict[str, tuple[t.Union[None, type, Schema], Field]]:
        return {
            name: (self._get_field_type(field), field) for name, field in self._schema_instance(schema).fields.items()
        }

    def is_schema(
        self, obj: t.Any
    ) -> compat.TypeGuard[t.Union[Schema, type[Schema]]]:  # PORT: Replace compat when stop supporting 3.9
        return isinstance(obj, Schema) or (inspect.isclass(obj) and issubclass(obj, Schema))

    def is_field(
        self, obj: t.Any
    ) -> compat.TypeGuard[t.Union[Field, type[Field]]]:  # PORT: Replace compat when stop supporting 3.9
        return isinstance(obj, Field) or (inspect.isclass(obj) and issubclass(obj, Field))

    def _schema_instance(self, schema: t.Union[type[Schema], Schema]) -> Schema:
        if inspect.isclass(schema) and issubclass(schema, Schema):
            return schema()
        elif isinstance(schema, Schema):
            return schema
        else:
            raise ValueError("Wrong schema")
