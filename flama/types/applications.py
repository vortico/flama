import enum

__all__ = ["AppStatus"]


class AppStatus(enum.Enum):
    NOT_INITIALIZED = enum.auto()
    STARTING = enum.auto()
    READY = enum.auto()
    SHUTTING_DOWN = enum.auto()
    SHUT_DOWN = enum.auto()
    FAILED = enum.auto()
