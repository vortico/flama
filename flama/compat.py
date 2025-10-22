import sys

__all__ = ["Self", "NotRequired", "StrEnum", "tomllib", "get_annotations"]

# PORT: Remove when stop supporting 3.10
# Self was added in Python 3.11
# https://docs.python.org/3/library/enum.html#enum.StrEnum
if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


# PORT: Remove when stop supporting 3.10
# NotRequired was added in Python 3.11
# https://docs.python.org/3/library/enum.html#enum.StrEnum
if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired


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

# PORT: Remove when stop supporting 3.13
# annotationlib.get_annotations was added in Python 3.14
# https://docs.python.org/3/library/annotationlib.html#annotationlib.get_annotations
if sys.version_info >= (3, 14):
    from annotationlib import get_annotations
else:
    from typing_extensions import get_annotations
