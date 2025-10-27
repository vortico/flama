import importlib.util
import sys

__all__ = ["NotInstalled", "installed"]


class NotInstalled(Exception): ...


def installed(module: str) -> bool:
    """Check if a module is installed.

    :param module: module name.
    :return: True if installed and importable.
    """
    return module in sys.modules or importlib.util.find_spec(module) is not None
