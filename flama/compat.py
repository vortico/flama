import sys

__all__ = ["Concatenate", "ParamSpec", "TypeGuard", "UnionType", "StrEnum", "tomllib"]

# PORT: Remove when stop supporting 3.9
# Concatenate was added in Python 3.10
# https://docs.python.org/3/library/typing.html#typing.Concatenate
if sys.version_info >= (3, 10):
    from typing import Concatenate
else:
    from typing_extensions import Concatenate


# PORT: Remove when stop supporting 3.9
# ParamSpec was added in Python 3.10
# https://docs.python.org/3/library/typing.html#typing.ParamSpec
if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec


# PORT: Remove when stop supporting 3.9
# TypeGuard was added in Python 3.10
# https://docs.python.org/3/library/typing.html#typing.TypeGuard
if sys.version_info >= (3, 10):
    from typing import TypeGuard
else:
    from typing_extensions import TypeGuard


# PORT: Remove when stop supporting 3.9
# UnionType was added in Python 3.10
# https://docs.python.org/3/library/stdtypes.html#types-union
if sys.version_info >= (3, 10):
    from types import UnionType
else:
    from typing import Union as UnionType


# PORT: Remove when stop supporting 3.10
# StrEnum was added in Python 3.11
# https://docs.python.org/3/library/enum.html#enum.StrEnum
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()


# PORT: Remove when stop supporting 3.10
# Tomllib was added in Python 3.11
# https://docs.python.org/3/library/tomllib.html
if sys.version_info >= (3, 11):  # PORT: Remove when stop supporting 3.10
    import tomllib
else:
    try:
        import tomli

        tomllib = tomli
    except ModuleNotFoundError:
        tomllib = None
