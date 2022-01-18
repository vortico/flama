import inspect
import typing

import marshmallow
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin, resolve_schema_cls

from flama.schemas._libs.marshmallow.fields import MAPPING
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError
from flama.schemas.utils import is_schema_class, is_schema_instance

__all__ = [
    "build_field",
    "build_schema",
    "validate",
    "load",
    "dump",
    "to_json_schema",
    "unique_instance",
]


def build_field(field_type: type, required: bool, default: typing.Any) -> marshmallow.fields.Field:
    if required:
        kwargs = {"required": required}
    else:
        kwargs = {"load_default": default}

    return MAPPING[field_type](**kwargs)


def build_schema(
    schema: marshmallow.Schema = None,
    pagination: type(marshmallow.Schema) = None,
    paginated_schema_name: str = None,
    name: str = "Schema",
    fields: typing.Dict[str, marshmallow.fields.Field] = None,
) -> type(marshmallow.Schema):
    if schema and not pagination:
        schema_class = schema if is_schema_class(schema) else schema.__class__
        return type(name, (schema_class,))

    if pagination:
        assert paginated_schema_name, "Parameter 'pagination_schema_name' must be given to create a paginated schema"
        data_item_schema = marshmallow.fields.Nested(schema) if schema else marshmallow.fields.Raw()
        return type(
            paginated_schema_name,
            (pagination,),
            {"data": marshmallow.fields.List(data_item_schema, required=True)},
        )

    return type(name, (marshmallow.Schema,), fields)


def validate(schema: marshmallow.Schema, values: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
    if is_schema_class(schema):
        schema = schema()

    try:
        return schema.load(values, unknown=marshmallow.EXCLUDE)
    except marshmallow.ValidationError as exc:
        raise SchemaValidationError(errors=exc.normalized_messages())


def load(schema: marshmallow.Schema, value: typing.Dict[str, typing.Any]) -> marshmallow.Schema:
    if is_schema_class(schema):
        schema = schema()

    return schema.load(value)


def dump(schema: marshmallow.Schema, value: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
    if is_schema_class(schema):
        schema = schema()

    try:
        return schema.dump(value)
    except Exception as exc:
        raise SchemaValidationError(errors=str(exc))


def to_json_schema(
    schema: typing.Union[type, marshmallow.Schema, marshmallow.fields.Field]
) -> typing.Dict[str, typing.Any]:
    try:
        plugin = MarshmallowPlugin(schema_name_resolver=lambda x: resolve_schema_cls(x).__name__)
        APISpec("", "", "3.1.0", [plugin])
        converter = plugin.converter

        if inspect.isclass(schema) and issubclass(schema, marshmallow.Schema):
            return converter.schema2jsonschema(schema)
        elif isinstance(schema, marshmallow.Schema):
            if getattr(schema, "many", False):
                return {"type": "array", "items": converter.schema2jsonschema(schema), "additionalItems": False}
            else:
                return converter.schema2jsonschema(schema)
        elif (inspect.isclass(schema) and issubclass(schema, marshmallow.fields.Field)) or isinstance(
            schema, marshmallow.fields.Field
        ):
            return converter.field2property(schema)
    except Exception as e:
        raise SchemaGenerationError from e


def unique_instance(schema: typing.Union[type, marshmallow.Schema]) -> marshmallow.Schema:
    if is_schema_instance(schema):
        return schema.__class__

    return schema
