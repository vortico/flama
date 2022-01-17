# flake8: noqa
import datetime
import uuid

from typesystem.fields import *
from typesystem.schemas import Reference

MAPPING = {
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
