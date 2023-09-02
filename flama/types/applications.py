import enum
import typing as t

__all__ = ["Tag", "AppStatus"]

Tag = t.Union[str, t.Sequence["Tag"], t.Dict[str, "Tag"]]


class AppStatus(enum.Enum):
    NOT_INITIALIZED = enum.auto()
    STARTING = enum.auto()
    READY = enum.auto()
    SHUTTING_DOWN = enum.auto()
    SHUT_DOWN = enum.auto()
    FAILED = enum.auto()
