import typing

__all__ = ["dict_safe_add"]


def dict_safe_add(d: typing.Dict, v: typing.Any, *keys):
    _d = d

    for k in keys[:-1]:
        if not _d.get(k):
            _d[k] = {}

        _d = _d[k]

    _d[keys[-1]] = v
