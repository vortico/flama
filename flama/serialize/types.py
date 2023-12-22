import enum
import sys

if sys.version_info < (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover

    class StrEnum(str, enum.Enum):
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

    enum.StrEnum = StrEnum  # type: ignore


class Framework(enum.StrEnum):  # type: ignore # PORT: Replace with enum.StrEnum when stop supporting 3.10
    """ML formats available for Flama serialization."""

    sklearn = enum.auto()
    tensorflow = enum.auto()
    torch = enum.auto()
    keras = enum.auto()
