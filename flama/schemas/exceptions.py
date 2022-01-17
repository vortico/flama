import typing

__all__ = ["SchemaError", "SchemaParseError", "SchemaValidationError", "SchemaGenerationError"]


class SchemaError(Exception):
    def __init__(self, errors: typing.Union[str, typing.Dict[str, typing.Any]], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = errors


class SchemaParseError(SchemaError):
    pass


class SchemaValidationError(SchemaError):
    pass


class SchemaGenerationError(Exception):
    pass
