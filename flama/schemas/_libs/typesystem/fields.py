# ruff: noqa
import datetime
import typing
import uuid

from typesystem.fields import *
from typesystem.schemas import Reference

MAPPING: typing.Dict[typing.Any, typing.Type[Field]] = {
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
