import inspect
import typing as t

import marshmallow
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin, resolve_schema_cls

from flama.schemas._libs.marshmallow.fields import MAPPING
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError

if t.TYPE_CHECKING:
    from apispec.ext.marshmallow import OpenAPIConverter

__all__ = ["MarshmallowAdapter"]


class MarshmallowAdapter(Adapter[marshmallow.Schema, marshmallow.fields.Field]):
    def build_field(self, field_type: t.Type, required: bool, default: t.Any) -> marshmallow.fields.Field:
        field_class = MAPPING[field_type]

        if required:
            return field_class(required=required)

        return field_class(load_default=default)

    def build_schema(
        self,
        schema: t.Optional[t.Union[marshmallow.Schema, t.Type[marshmallow.Schema]]] = None,
        pagination: t.Optional[t.Union[marshmallow.Schema, t.Type[marshmallow.Schema]]] = None,
        paginated_schema_name: str = None,
        name: str = "Schema",
        fields: t.Optional[t.Dict[str, marshmallow.fields.Field]] = None,
    ) -> t.Type[marshmallow.Schema]:
        schema_fields: t.Dict[str, t.Union[marshmallow.fields.Field, t.Type]]
        parent_schema: t.Optional[marshmallow.Schema] = None
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

        return marshmallow.Schema.from_dict(schema_fields, name=name)

    def validate(
        self,
        schema: t.Union[t.Type[marshmallow.Schema], marshmallow.Schema],
        values: t.Dict[str, t.Any],
    ) -> t.Dict[str, t.Any]:
        schema_instance = schema() if inspect.isclass(schema) else schema

        try:
            data: t.Dict[str, t.Any] = schema_instance.load(values, unknown=marshmallow.EXCLUDE)
        except marshmallow.ValidationError as exc:
            raise SchemaValidationError(errors=exc.normalized_messages())

        return data

    def load(
        self,
        schema: t.Union[t.Type[marshmallow.Schema], marshmallow.Schema],
        value: t.Dict[str, t.Any],
    ) -> marshmallow.Schema:
        schema_instance = schema() if inspect.isclass(schema) else schema

        load_schema: marshmallow.Schema = schema_instance.load(value)

        return load_schema

    def dump(
        self,
        schema: t.Union[t.Type[marshmallow.Schema], marshmallow.Schema],
        value: t.Dict[str, t.Any],
    ) -> t.Dict[str, t.Any]:
        schema_instance = schema() if inspect.isclass(schema) else schema

        try:
            data: t.Dict[str, t.Any] = schema_instance.dump(value)
        except Exception as exc:
            raise SchemaValidationError(errors=str(exc))

        return data

    def to_json_schema(
        self,
        schema: t.Union[
            t.Type[marshmallow.Schema],
            t.Type[marshmallow.fields.Field],
            marshmallow.Schema,
            marshmallow.fields.Field,
        ],
    ) -> t.Dict[str, t.Any]:
        json_schema: t.Dict[str, t.Any]
        try:
            plugin = MarshmallowPlugin(
                schema_name_resolver=lambda x: resolve_schema_cls(x).__name__  # type: ignore[no-any-return]
            )
            APISpec("", "", "3.1.0", [plugin])
            converter: "OpenAPIConverter" = plugin.converter  # type: ignore[assignment]

            if (inspect.isclass(schema) and issubclass(schema, marshmallow.fields.Field)) or isinstance(
                schema, marshmallow.fields.Field
            ):
                json_schema = converter.field2property(schema)  # type: ignore[arg-type]
            elif inspect.isclass(schema) and issubclass(schema, marshmallow.Schema):
                json_schema = converter.schema2jsonschema(schema)
            elif isinstance(schema, marshmallow.Schema):
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

    def unique_schema(
        self, schema: t.Union[marshmallow.Schema, t.Type[marshmallow.Schema]]
    ) -> t.Type[marshmallow.Schema]:
        if isinstance(schema, marshmallow.Schema):
            return schema.__class__

        return schema

    def is_schema(self, schema: t.Union[marshmallow.Schema, t.Type[marshmallow.Schema]]) -> bool:
        return isinstance(schema, marshmallow.Schema) or (
            inspect.isclass(schema) and issubclass(schema, marshmallow.Schema)
        )

    def is_field(self, obj: t.Union[marshmallow.fields.Field, t.Type[marshmallow.fields.Field]]) -> bool:
        return isinstance(obj, marshmallow.fields.Field) or (
            inspect.isclass(obj) and issubclass(obj, marshmallow.fields.Field)
        )
