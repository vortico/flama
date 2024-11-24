import enum

from flama import compat


class Framework(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
    """ML formats available for Flama serialization."""

    sklearn = enum.auto()
    tensorflow = enum.auto()
    torch = enum.auto()
    keras = enum.auto()
