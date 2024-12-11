import enum
import typing as t

from flama import compat

__all__ = ["FileFormat"]

UnknownType = t.NewType("UnknownType", str)


class FileFormat(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
    """Config file format."""

    ini = enum.auto()
    json = enum.auto()
    yaml = enum.auto()
    toml = enum.auto()
