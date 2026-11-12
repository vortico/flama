import typing as t

from flama import types

__all__ = ["SchemaError", "SchemaParseError", "SchemaValidationError", "SchemaGenerationError"]


class SchemaError(Exception):
    """Base exception for the errors a schema library reports.

    Whatever shape the library reports them in, they are held as one RFC 9457 error detail per message.

    :param errors: Errors as the schema library reports them.
    """

    def __init__(self, errors: t.Any, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors: list[types.ErrorDetail] = [
            types.ErrorDetail(
                detail=detail, pointer="#" + "".join(f"/{x.replace('~', '~0').replace('/', '~1')}" for x in path)
            )
            for path, detail in self._details(errors, ())
        ]

    def __str__(self) -> str:
        return "\n".join(
            f"{x.pointer.removeprefix('#/')}: {x.detail}" if x.pointer != "#" else x.detail for x in self.errors
        )

    @classmethod
    def _details(cls, errors: t.Any, path: tuple[str, ...]) -> t.Iterator[tuple[tuple[str, ...], str]]:
        """The messages reported for a value, or for each value nested in it, with the path to each.

        :param errors: A message, a list of them, a pydantic error, or the errors of nested values.
        :param path: Path to the value the errors belong to.
        :return: A path and a message for each message.
        """
        if isinstance(errors, t.Mapping) and isinstance(errors.get("msg"), str) and "type" in errors:
            location = errors.get("loc")
            yield (tuple(str(x) for x in location) if isinstance(location, list | tuple) else path), errors["msg"]
        elif isinstance(errors, t.Mapping):
            for key, value in errors.items():
                # Marshmallow reports errors of the value as a whole under this key.
                yield from cls._details(value, path if key == "_schema" else (*path, str(key)))
        elif isinstance(errors, list | tuple):
            for error in errors:
                yield from cls._details(error, path)
        else:
            yield path, str(errors)


class SchemaParseError(SchemaError):
    pass


class SchemaValidationError(SchemaError):
    pass


class SchemaGenerationError(Exception):
    pass
