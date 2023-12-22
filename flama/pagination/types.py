import enum
import sys

if sys.version_info < (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover

    class StrEnum(str, enum.Enum):
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

    enum.StrEnum = StrEnum  # type: ignore

__all__ = ["PaginationType"]


class PaginationType(enum.StrEnum):  # type: ignore # PORT: Remove this comment when stop supporting 3.10
    page_number = enum.auto()
    limit_offset = enum.auto()
