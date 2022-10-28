import functools
import importlib.util
import sys
import typing

import pytest


def installed(module: str) -> bool:
    """Check if a module is installed.

    :param module: module name.
    :return: True if installed and importable.
    """
    return module in sys.modules or importlib.util.find_spec(module) is not None


class check_param_lib_installed:
    def __init__(self, func):
        self.func = func
        functools.update_wrapper(self, func)

    def __call__(self, request, *args, **kwargs):
        if not installed(request.param):
            pytest.skip(f"Lib '{request.param}' is not installed.")
            return
        return self.func(request, *args, **kwargs)

    def __get__(self, instance, owner=None):
        return self.func.__get__(instance, owner)


class ExceptionContext:
    def __init__(self, context, exception: typing.Optional[Exception] = None):
        self.context = context
        self.exception = exception

    def __enter__(self):
        return self.context.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.context.__exit__(exc_type, exc_val, exc_tb)
