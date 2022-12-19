import asyncio
import functools
import sys
import typing as t

from starlette.concurrency import run_in_threadpool

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import ParamSpec, TypeGuard

    t.TypeGuard = TypeGuard
    t.ParamSpec = ParamSpec

__all__ = ["is_async", "run"]

T = t.TypeVar("T", covariant=True)
P = t.ParamSpec("P")


def is_async(obj: t.Any) -> t.TypeGuard[t.Callable[..., t.Awaitable]]:
    """Check if given object is an async function, callable or partialised function.

    :param obj: Object to check.
    :return: True if it's an async function, callable or partialised function.
    """
    while isinstance(obj, functools.partial):
        obj = obj.func

    return asyncio.iscoroutinefunction(obj) or (
        callable(obj) and asyncio.iscoroutinefunction(obj.__call__)  # type: ignore[operator]
    )


async def run(func: t.Callable[P, t.Union[T, t.Awaitable[T]]], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run a function either as asyncio awaiting it if it's an async function or running it in a threadpool if it's a
    sync function.

    :param func: Function to run.
    :param args: Positional arguments.
    :param kwargs: Keyword arguments.
    :return: Function returned value.
    """
    if is_async(func):
        return await func(*args, **kwargs)  # type: ignore[no-any-return]

    return await run_in_threadpool(func, *args, **kwargs)  # type: ignore[arg-type]
