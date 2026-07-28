# ruff: noqa
import datetime
import decimal
import typing as t
import uuid

from typesystem.fields import *
from typesystem.schemas import Reference

from flama.http.data_structures import UploadFile

__all__ = ["File", "MAPPING", "MAPPING_TYPES"]


class File(String):
    """A file within a request body.

    Extends :class:`typesystem.String` so that it renders as ``{"type": "string", "format": "binary"}``,
    the JSON Schema representation of a binary payload. Its value is an
    :class:`~flama.http.UploadFile` rather than a string, so validation is an instance check.
    """

    errors = {**String.errors, "type": "Must be a file upload."}

    def __init__(self, **kwargs: t.Any) -> None:
        kwargs.setdefault("format", "binary")
        super().__init__(**kwargs)
        self.allow_blank = True

    def validate(self, value: t.Any, *, strict: bool = False) -> UploadFile:
        if not isinstance(value, UploadFile):
            raise self.validation_error("type")

        return value


MAPPING: dict[type | None, type[Field]] = {
    None: Field,
    int: Integer,
    float: Float,
    str: String,
    bool: Boolean,
    list: Array,
    dict: Object,
    uuid.UUID: String,
    decimal.Decimal: Decimal,
    datetime.date: Date,
    datetime.datetime: DateTime,
    datetime.time: Time,
    UploadFile: File,
}

MAPPING_TYPES = {v: k for k, v in MAPPING.items()}
