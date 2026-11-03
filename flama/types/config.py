import enum

from flama import _compat

__all__ = ["Empty", "Unknown", "FileFormat"]


Empty = _compat.sentinel("Empty")
Unknown = _compat.sentinel("Unknown")


class FileFormat(enum.StrEnum):
    """Config file format."""

    ini = enum.auto()
    json = enum.auto()
    yaml = enum.auto()
    toml = enum.auto()
