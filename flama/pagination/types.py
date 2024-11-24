import enum

from flama import compat

__all__ = ["PaginationType"]


class PaginationType(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
    page_number = enum.auto()
    limit_offset = enum.auto()
