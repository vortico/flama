import enum

__all__ = ["FileFormat"]


class FileFormat(enum.Enum):
    """Config file format."""

    INI = enum.auto()
    JSON = enum.auto()
    YAML = enum.auto()
    TOML = enum.auto()
