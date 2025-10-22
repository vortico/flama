# ruff: noqa
import datetime
import typing as t
import uuid

from marshmallow.fields import *

MAPPING: t.Dict[type | None, type[Field]] = {
    None: Field,
    int: Integer,
    float: Float,
    str: String,
    bool: Boolean,
    list: List,
    dict: Dict,
    uuid.UUID: UUID,
    datetime.date: Date,
    datetime.datetime: DateTime,
    datetime.time: Time,
}

MAPPING_TYPES = {v: k for k, v in MAPPING.items()}
