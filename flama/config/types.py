import enum
import sys

__all__ = ["FileFormat"]

if sys.version_info < (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover

    class StrEnum(str, enum.Enum):
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

    enum.StrEnum = StrEnum  # type: ignore


class FileFormat(enum.StrEnum):  # type: ignore # PORT: Remove this comment when stop supporting 3.10
    """Config file format."""

    ini = enum.auto()
    json = enum.auto()
    yaml = enum.auto()
    toml = enum.auto()
