import inspect
import typing

import marshmallow
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin, resolve_schema_cls

from flama.schemas._libs.marshmallow.fields import MAPPING
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError

__all__ = ["MarshmallowAdapter"]


class MarshmallowAdapter(Adapter[marshmallow.Schema, marshmallow.fields.Field]):
    def build_field(self, field_type: typing.Type, required: bool, default: typing.Any) -> marshmallow.fields.Field:
        kwargs: typing.Dict[str, typing.Any] = {"required": required} if required else {"load_default": default}
        return MAPPING[field_type](**kwargs)

    def build_schema(  # type: ignore[override]
        self,
        schema: typing.Type[marshmallow.Schema] = None,
        pagination: typing.Type[marshmallow.Schema] = None,
        paginated_schema_name: str = None,
        name: str = "Schema",
        fields: typing.Dict[str, marshmallow.fields.Field] = None,
    ) -> typing.Type[marshmallow.Schema]:
        if schema and not pagination:
            return type(name, (schema.__class__ if isinstance(schema, marshmallow.Schema) else schema,), {})

        if pagination:
            assert paginated_schema_name, "Parameter 'pagination_schema_name' must be given to create a paginated field"
            data_item_schema = marshmallow.fields.Nested(schema) if schema else marshmallow.fields.Raw()
            return type(
                paginated_schema_name,
                (pagination,),
                {"data": marshmallow.fields.List(data_item_schema, required=True)},
            )

        if fields is None:
            fields = {}

        return type(name, (marshmallow.Schema,), fields.copy())

    def validate(
        self,
        schema: typing.Union[typing.Type[marshmallow.Schema], marshmallow.Schema],
        values: typing.Dict[str, typing.Any],
    ) -> typing.Dict[str, typing.Any]:
        schema_instance = schema() if inspect.isclass(schema) else schema

        try:
            data: typing.Dict[str, typing.Any] = schema_instance.load(values, unknown=marshmallow.EXCLUDE)
        except marshmallow.ValidationError as exc:
            raise SchemaValidationError(errors=exc.normalized_messages())

        return data

    def load(
        self,
        schema: typing.Union[typing.Type[marshmallow.Schema], marshmallow.Schema],
        value: typing.Dict[str, typing.Any],
    ) -> marshmallow.Schema:
        schema_instance = schema() if inspect.isclass(schema) else schema

        load_schema: marshmallow.Schema = schema_instance.load(value)

        return load_schema

    def dump(
        self,
        schema: typing.Union[typing.Type[marshmallow.Schema], marshmallow.Schema],
        value: typing.Dict[str, typing.Any],
    ) -> typing.Dict[str, typing.Any]:
        schema_instance = schema() if inspect.isclass(schema) else schema

        try:
            data: typing.Dict[str, typing.Any] = schema_instance.dump(value)
        except Exception as exc:
            raise SchemaValidationError(errors=str(exc))

        return data

    def to_json_schema(
        self,
        schema: typing.Union[
            typing.Type[marshmallow.Schema],
            typing.Type[marshmallow.fields.Field],
            marshmallow.Schema,
            marshmallow.fields.Field,
        ],
    ) -> typing.Dict[str, typing.Any]:
        json_schema: typing.Dict[str, typing.Any]
        try:
            plugin = MarshmallowPlugin(schema_name_resolver=lambda x: resolve_schema_cls(x).__name__)
            APISpec("", "", "3.1.0", [plugin])
            converter = plugin.converter

            if (inspect.isclass(schema) and issubclass(schema, marshmallow.fields.Field)) or isinstance(
                schema, marshmallow.fields.Field
            ):
                json_schema = converter.field2property(schema)
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

    def unique_schema(  # type: ignore[override]
        self, schema: typing.Union[typing.Type[marshmallow.Schema], marshmallow.Schema]
    ) -> typing.Type[marshmallow.Schema]:
        if isinstance(schema, marshmallow.Schema):
            return schema.__class__

        return schema

    def is_schema(self, schema: typing.Union[marshmallow.Schema, typing.Type[marshmallow.Schema]]) -> bool:
        return isinstance(schema, marshmallow.Schema) or (
            inspect.isclass(schema) and issubclass(schema, marshmallow.Schema)
        )

    def is_field(self, obj: typing.Union[marshmallow.fields.Field, typing.Type[marshmallow.fields.Field]]) -> bool:
        return isinstance(obj, marshmallow.fields.Field) or (
            inspect.isclass(obj) and issubclass(obj, marshmallow.fields.Field)
        )
