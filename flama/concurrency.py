import asyncio
import functools
import multiprocessing
import sys
import typing as t

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import ParamSpec, TypeGuard

    t.TypeGuard = TypeGuard
    t.ParamSpec = ParamSpec

__all__ = ["is_async", "run", "run"]

R = t.TypeVar("R", covariant=True)
P = t.ParamSpec("P")


def is_async(obj: t.Any) -> t.TypeGuard[t.Callable[..., t.Awaitable[t.Any]]]:
    """Check if given object is an async function, callable or partialised function.

    :param obj: Object to check.
    :return: True if it's an async function, callable or partialised function.
    """
    while isinstance(obj, functools.partial):
        obj = obj.func

    return asyncio.iscoroutinefunction(obj) or (callable(obj) and asyncio.iscoroutinefunction(obj.__call__))


async def run(
    func: t.Union[t.Callable[P, R], t.Callable[P, t.Awaitable[R]]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """Run a function either as asyncio awaiting it if it's an async function or running it in a thread if it's a
    sync function.

    :param func: Function to run.
    :param args: Positional arguments.
    :param kwargs: Keyword arguments.
    :return: Function returned value.
    """
    if is_async(func):
        return await func(*args, **kwargs)

    return await asyncio.to_thread(func, *args, **kwargs)  # type: ignore


class AsyncProcess(multiprocessing.Process):
    """Multiprocessing Process class whose target is an async function."""

    def run(self):
        if self._target:  # type: ignore
            task = self._target(*self._args, **self._kwargs)  # type: ignore

            if is_async(self._target):  # type: ignore
                policy = asyncio.get_event_loop_policy()
                loop = policy.new_event_loop()
                policy.set_event_loop(loop)
                loop.run_until_complete(task)
