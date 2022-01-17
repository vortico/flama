import typing

import typesystem

from flama.schemas._libs.typesystem.fields import MAPPING
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError

__all__ = [
    "build_field",
    "build_schema",
    "validate",
    "load",
    "dump",
    "to_json_schema",
    "unique_instance",
]


def build_field(field_type: type, required: bool, default: typing.Any, **kwargs) -> typesystem.fields.Field:
    if required is False and default is None:
        kwargs["allow_null"] = True
    else:
        kwargs["default"] = default

    return MAPPING[field_type](**kwargs)


def build_schema(
    schema: typesystem.Schema = None,
    pagination: typesystem.Schema = None,
    paginated_schema_name: str = None,
    name: str = "Schema",
    fields: typing.Dict[str, typesystem.Field] = None,
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


def validate(schema: typesystem.Schema, values: typing.Dict[str, typing.Any]) -> typing.Any:
    try:
        return schema.validate(values)
    except typesystem.ValidationError as errors:
        raise SchemaValidationError(errors={k: [v] for k, v in errors.items()})


def load(schema: type(typesystem.Schema), value: typing.Dict[str, typing.Any]) -> typesystem.Schema:
    return schema.validate(value)


def dump(
    schema: typing.Union[typesystem.fields.Field, type(typesystem.Schema)], value: typing.Dict[str, typing.Any]
) -> typing.Any:
    return _dump(validate(schema, value))


def _dump(value: typing.Dict[str, typing.Any]) -> typing.Any:
    if isinstance(value, typesystem.Schema):
        return dict(value)

    if isinstance(value, list):
        return [_dump(x) for x in value]

    return value


def to_json_schema(
    schema: typing.Union[type, typesystem.Schema, typesystem.fields.Field]
) -> typing.Dict[str, typing.Any]:
    try:
        json_schema = typesystem.to_json_schema(schema)
        json_schema.pop("components", None)
        return json_schema
    except Exception as e:
        raise SchemaGenerationError from e


def unique_instance(schema: typing.Union[typesystem.Schema, typesystem.Array]) -> typesystem.Schema:
    if isinstance(schema, typesystem.Array):
        if not isinstance(schema.items, typesystem.Reference):
            raise ValueError("Schema cannot be resolved")

        return schema.items.target

    return schema
