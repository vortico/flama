import enum

from flama import compat

__all__ = ["Empty", "Unknown", "FileFormat"]


Empty = compat.sentinel("Empty")
Unknown = compat.sentinel("Unknown")


class FileFormat(enum.StrEnum):
    """Config file format."""

    ini = enum.auto()
    json = enum.auto()
    yaml = enum.auto()
    toml = enum.auto()
