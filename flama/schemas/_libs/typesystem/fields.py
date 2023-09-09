# ruff: noqa
import datetime
import typing as t
import uuid

from typesystem.fields import *
from typesystem.schemas import Reference

MAPPING: t.Dict[t.Union[t.Type, None], t.Type[Field]] = {
    None: Field,
    int: Integer,
    float: Float,
    str: String,
    bool: Boolean,
    list: Array,
    dict: Object,
    uuid.UUID: String,
    datetime.date: Date,
    datetime.datetime: DateTime,
    datetime.time: Time,
}

MAPPING_TYPES = {v: k for k, v in MAPPING.items()}
