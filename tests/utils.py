import importlib.util
import sys
import typing


def installed(module: str) -> bool:
    """Check if a module is installed.

    :param module: module name.
    :return: True if installed and importable.
    """
    return module in sys.modules or importlib.util.find_spec(module) is not None


class ExceptionContext:
    def __init__(self, context, exception: typing.Optional[Exception] = None):
        self.context = context
        self.exception = exception

    def __enter__(self):
        return self.context.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.context.__exit__(exc_type, exc_val, exc_tb)
