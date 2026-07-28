# ruff: noqa
import datetime
import decimal
import typing as t
import uuid

import marshmallow
from marshmallow.fields import *

from flama.http.data_structures import UploadFile

__all__ = ["File", "MAPPING", "MAPPING_TYPES"]


class File(String):
    """A file within a request body.

    Extends :class:`marshmallow.fields.String` so that it renders as
    ``{"type": "string", "format": "binary"}``, the JSON Schema representation of a binary payload. Its
    value is an :class:`~flama.http.UploadFile` rather than a string, so deserialisation is an instance
    check.
    """

    def __init__(self, **kwargs: t.Any) -> None:
        kwargs["metadata"] = {"format": "binary", **kwargs.get("metadata", {})}
        super().__init__(**kwargs)

    def _deserialize(  # ty: ignore[invalid-method-override]
        self, value: t.Any, attr: t.Any, data: t.Any, **kwargs: t.Any
    ) -> UploadFile:
        if not isinstance(value, UploadFile):
            raise marshmallow.ValidationError("Not a valid file upload.")

        return value

    def _serialize(self, value: t.Any, attr: t.Any, obj: t.Any, **kwargs: t.Any) -> t.Any:
        return value


MAPPING: dict[type | None, type[Field]] = {
    None: Field,
    int: Integer,
    float: Float,
    str: String,
    bool: Boolean,
    list: List,
    dict: Dict,
    uuid.UUID: UUID,
    decimal.Decimal: Decimal,
    datetime.date: Date,
    datetime.datetime: DateTime,
    datetime.time: Time,
    UploadFile: File,
}

MAPPING_TYPES = {v: k for k, v in MAPPING.items()}
