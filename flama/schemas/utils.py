import inspect
import typing

from flama import schemas

__all__ = [
    "is_schema_class",
    "is_schema_instance",
    "is_schema",
    "is_field_class",
    "is_field_instance",
    "is_field",
]


def is_schema_class(schema: typing.Any) -> bool:
    return inspect.isclass(schema) and issubclass(schema, schemas.Schema)


def is_schema_instance(schema: typing.Any) -> bool:
    return isinstance(schema, schemas.Schema)


def is_schema(schema: typing.Any) -> bool:
    return is_schema_class(schema) or is_schema_instance(schema)


def is_field_class(field: typing.Any) -> bool:
    return inspect.isclass(field) and issubclass(field, schemas.Field)


def is_field_instance(field: typing.Any) -> bool:
    return isinstance(field, schemas.Field)


def is_field(field: typing.Any) -> bool:
    return is_field_class(field) or is_field_instance(field)
