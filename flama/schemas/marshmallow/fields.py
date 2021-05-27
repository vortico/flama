# flake8: noqa
import datetime
import uuid

from marshmallow.fields import *

MAPPING = {
    int: Integer,
    float: Number,
    str: String,
    bool: Boolean,
    list: List,
    dict: Dict,
    uuid.UUID: UUID,
    datetime.date: Date,
    datetime.datetime: DateTime,
    datetime.time: Time,
}
