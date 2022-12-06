import inspect
import sys
import typing as t

import marshmallow
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin, resolve_schema_cls

from flama.injection import Parameter
from flama.schemas._libs.marshmallow.fields import MAPPING
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard
else:  # pragma: no cover
    from typing_extensions import TypeGuard

if t.TYPE_CHECKING:
    from apispec.ext.marshmallow import OpenAPIConverter

__all__ = ["MarshmallowAdapter"]

Schema = marshmallow.Schema
Field = marshmallow.fields.Field


class MarshmallowAdapter(Adapter[Schema, Field]):
    def build_field(
        self,
        name: str,
        type: t.Type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        **kwargs: t.Any
    ) -> Field:
        field_args = {
            "required": required,
            "allow_none": nullable,
            "metadata": {**kwargs, "title": name},
        }

        if not required:
            field_args["load_default"] = default if default is not Parameter.empty else None

        return MAPPING[type](**field_args)  # type: ignore[arg-type]

    def build_schema(
        self,
        name: str = "Schema",
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        pagination: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        paginated_schema_name: t.Optional[str] = None,
        fields: t.Optional[t.Dict[str, Field]] = None,
    ) -> t.Type[Schema]:
        schema_fields: t.Dict[str, t.Union[Field, t.Type]]
        parent_schema: t.Optional[Schema] = None
        if inspect.isclass(schema):
            parent_schema = schema()

        if pagination:
            assert paginated_schema_name, "Parameter 'pagination_schema_name' must be given to create a paginated field"
            pagination_schema = pagination() if inspect.isclass(pagination) else pagination
            data_field = marshmallow.fields.Nested(parent_schema) if parent_schema else marshmallow.fields.Raw()
            schema_fields = {
                **pagination_schema.fields,
                "data": marshmallow.fields.List(data_field, required=True),
            }
            name = paginated_schema_name
        else:
            schema_fields = {
                **(parent_schema.fields if parent_schema else {}),
                **(fields or {}),
            }

        return Schema.from_dict(schema_fields, name=name)

    def validate(self, schema: t.Union[t.Type[Schema], Schema], values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        schema_instance = schema() if inspect.isclass(schema) else schema

        try:
            data: t.Dict[str, t.Any] = schema_instance.load(values, unknown=marshmallow.EXCLUDE)
        except marshmallow.ValidationError as exc:
            raise SchemaValidationError(errors=exc.normalized_messages())

        return data

    def load(self, schema: t.Union[t.Type[Schema], Schema], value: t.Dict[str, t.Any]) -> Schema:
        schema_instance = schema() if inspect.isclass(schema) else schema

        load_schema: Schema = schema_instance.load(value)

        return load_schema

    def dump(self, schema: t.Union[t.Type[Schema], Schema], value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        schema_instance = schema() if inspect.isclass(schema) else schema

        try:
            data: t.Dict[str, t.Any] = schema_instance.dump(value)
        except Exception as exc:
            raise SchemaValidationError(errors=str(exc))

        return data

    def to_json_schema(self, schema: t.Union[t.Type[Schema], t.Type[Field], Schema, Field]) -> t.Dict[str, t.Any]:
        json_schema: t.Dict[str, t.Any]
        try:
            plugin = MarshmallowPlugin(
                schema_name_resolver=lambda x: resolve_schema_cls(x).__name__  # type: ignore[no-any-return]
            )
            APISpec("", "", "3.1.0", [plugin])
            converter: "OpenAPIConverter" = plugin.converter  # type: ignore[assignment]

            if (inspect.isclass(schema) and issubclass(schema, Field)) or isinstance(schema, Field):
                json_schema = converter.field2property(schema)  # type: ignore[arg-type]
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

    def is_schema(self, obj: t.Any) -> TypeGuard[t.Union[Schema, t.Type[Schema]]]:
        return isinstance(obj, Schema) or (inspect.isclass(obj) and issubclass(obj, Schema))

    def is_field(self, obj: t.Any) -> TypeGuard[t.Union[Field, t.Type[Field]]]:
        return isinstance(obj, Field) or (inspect.isclass(obj) and issubclass(obj, Field))
