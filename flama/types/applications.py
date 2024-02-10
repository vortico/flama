import enum
import sys
import typing as t

if t.TYPE_CHECKING:
    from flama import Flama


if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard  # type: ignore


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
) -> t.TypeGuard["Flama"]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
    """Checks if an object is an instance of Flama.

    :param obj: The object to check.
    :return: True if the object is an instance of Flama, False otherwise.
    """
    from flama import Flama

    return isinstance(obj, Flama)
