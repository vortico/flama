# ruff: noqa
import typing as t

import pydantic
from pydantic_core import core_schema

from flama.http.data_structures import UploadFile

__all__ = ["File", "MAPPING", "MAPPING_TYPES"]


File = t.Annotated[
    UploadFile,
    pydantic.GetPydanticSchema(lambda source, handler: core_schema.is_instance_schema(UploadFile)),
    pydantic.WithJsonSchema({"type": "string", "format": "binary"}),
]
"""A file within a request body, rendered as ``{"type": "string", "format": "binary"}``.

Pydantic builds its validation and JSON Schema from the annotation itself, so unlike the fields of
other schema libraries this is a type to annotate with rather than a field to instantiate.
"""


MAPPING: dict[type | None, t.Any] = {
    UploadFile: File,
}

MAPPING_TYPES = {v: k for k, v in MAPPING.items()}
