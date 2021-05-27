import inspect
import typing

import marshmallow
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin

from flama.schemas.base import ValidationError


def build_schema(fields: typing.Dict[str, marshmallow.fields.Field]) -> type(marshmallow.Schema):
    return type("Schema", (marshmallow.Schema,), fields)()


def validate(schema: marshmallow.Schema, values: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
    try:
        return schema.load(values, unknown=marshmallow.EXCLUDE)
    except marshmallow.ValidationError as exc:
        raise ValidationError(errors=exc.normalized_messages())


def parse(value: typing.Dict[str, typing.Any]) -> marshmallow.Schema:
    pass


def to_json_schema(schema: typing.Union[type, marshmallow.Schema, marshmallow.fields.Field]):
    plugin = MarshmallowPlugin()
    APISpec("", "", "3.0.1", [plugin])
    converter = plugin.converter
    if inspect.isclass(schema) and issubclass(schema, marshmallow.Schema):
        return converter.schema2jsonschema(schema)
    elif isinstance(schema, marshmallow.Schema):
        if getattr(schema, "many", False):
            return {"type": "array", "items": converter.schema2jsonschema(schema)}
        else:
            return converter.schema2jsonschema(schema)
    elif (inspect.isclass(schema) and issubclass(schema, marshmallow.fields.Field)) or isinstance(
        schema, marshmallow.fields.Field
    ):
        return converter.field2property(schema)
