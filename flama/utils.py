import typing

import inspect
import marshmallow
from dataclasses import is_dataclass

__all__ = ["dict_safe_add"]


def dict_safe_add(d: typing.Dict, v: typing.Any, *keys):
    _d = d

    for k in keys[:-1]:
        if not _d.get(k):
            _d[k] = {}

        _d = _d[k]

    _d[keys[-1]] = v


def is_marshmallow_schema(obj):
    return inspect.isclass(obj) and issubclass(obj, marshmallow.Schema)


def is_marshmallow_dataclass(obj):
    return is_dataclass(obj) and hasattr(obj, 'Schema') and is_marshmallow_schema(obj.Schema)
