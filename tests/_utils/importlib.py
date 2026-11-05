import importlib.util
import sys

from flama import _imports

__all__ = ["NotInstalled", "installed", "missing"]


class NotInstalled(Exception): ...


def installed(module: str) -> bool:
    """Check if a module is installed.

    :param module: module name.
    :return: True if installed and importable.
    """
    return module in sys.modules or importlib.util.find_spec(module) is not None


def missing(package: _imports.DependencyName, submodule: str | None = None) -> _imports.Dependency:
    """Build a lazy module whose package reports itself as not installed.

    :param package: Optional package the module belongs to.
    :param submodule: Submodule of the package, if any.
    :return: Lazy module raising the package's error on use.
    """
    module = _imports.Dependency(package, submodule)
    module.available = False
    return module
