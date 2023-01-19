# ruff: noqa
import datetime
import typing
import uuid

import marshmallow.fields
from marshmallow.fields import *

MAPPING: typing.Dict[typing.Optional[typing.Type], typing.Type[marshmallow.fields.Field]] = {
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
