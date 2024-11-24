import asyncio
import functools
import multiprocessing
import sys
import typing as t

from flama import compat

__all__ = ["is_async", "run", "run_task_group", "AsyncProcess"]

R = t.TypeVar("R", covariant=True)
P = compat.ParamSpec("P")  # PORT: Replace compat when stop supporting 3.9


def is_async(
    obj: t.Any,
) -> compat.TypeGuard[t.Callable[..., t.Awaitable[t.Any]]]:  # PORT: Replace compat when stop supporting 3.9
    """Check if given object is an async function, callable or partialised function.

    :param obj: Object to check.
    :return: True if it's an async function, callable or partialised function.
    """
    while isinstance(obj, functools.partial):
        obj = obj.func

    return asyncio.iscoroutinefunction(obj) or asyncio.iscoroutinefunction(getattr(obj, "__call__"))


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

    return t.cast(R, await asyncio.to_thread(func, *args, **kwargs))


if sys.version_info >= (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover

    async def run_task_group(*tasks: t.Coroutine[t.Any, t.Any, t.Any]) -> list[asyncio.Task]:
        """Run a group of tasks.

        :param tasks: Tasks to run.
        :result: Finished tasks.
        """
        async with asyncio.TaskGroup() as task_group:
            return [task_group.create_task(task) for task in tasks]

else:  # pragma: no cover

    async def run_task_group(*tasks: t.Coroutine[t.Any, t.Any, t.Any]) -> list[asyncio.Task]:
        """Run a group of tasks.

        :param tasks: Tasks to run.
        :result: Finished tasks.
        """
        tasks_list = [asyncio.create_task(task) for task in tasks]
        await asyncio.wait(tasks_list)
        return tasks_list


class AsyncProcess(multiprocessing.Process):
    """Multiprocessing Process class whose target is an async function."""

    _target: t.Optional[t.Callable[..., t.Union[t.Any, t.Coroutine]]]
    _args: list[t.Any]
    _kwargs: dict[str, t.Any]

    def run(self) -> None:
        if self._target:
            result_or_task = self._target(*self._args, **self._kwargs)

            asyncio.run(result_or_task) if is_async(self._target) else result_or_task
