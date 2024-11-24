import enum
import typing as t

from flama import compat

if t.TYPE_CHECKING:
    from flama import Flama


__all__ = ["AppStatus", "is_flama_instance"]


class AppStatus(enum.Enum):
    NOT_STARTED = enum.auto()
    STARTING = enum.auto()
    READY = enum.auto()
    SHUTTING_DOWN = enum.auto()
    SHUT_DOWN = enum.auto()
    FAILED = enum.auto()


def is_flama_instance(
    obj: t.Any,
) -> compat.TypeGuard["Flama"]:  # PORT: Replace compat when stop supporting 3.9
    """Checks if an object is an instance of Flama.

    :param obj: The object to check.
    :return: True if the object is an instance of Flama, False otherwise.
    """
    from flama import Flama

    return isinstance(obj, Flama)
