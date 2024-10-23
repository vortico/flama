import asyncio
import functools
import multiprocessing
import sys
import typing as t

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import ParamSpec, TypeGuard

    t.TypeGuard = TypeGuard  # type: ignore
    t.ParamSpec = ParamSpec  # type: ignore

__all__ = ["is_async", "run", "run_task_group", "AsyncProcess"]

R = t.TypeVar("R", covariant=True)
P = t.ParamSpec("P")  # type: ignore # PORT: Remove this comment when stop supporting 3.9


def is_async(
    obj: t.Any,
) -> t.TypeGuard[  # type: ignore # PORT: Remove this comment when stop supporting 3.9
    t.Callable[..., t.Awaitable[t.Any]]
]:
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


if sys.version_info < (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover

    async def run_task_group(*tasks: t.Coroutine[t.Any, t.Any, t.Any]) -> t.List[asyncio.Task]:
        """Run a group of tasks.

        :param tasks: Tasks to run.
        :result: Finished tasks.
        """
        tasks_list = [asyncio.create_task(task) for task in tasks]
        await asyncio.wait(tasks_list)
        return tasks_list

else:  # noqa

    async def run_task_group(*tasks: t.Coroutine[t.Any, t.Any, t.Any]) -> t.List[asyncio.Task]:
        """Run a group of tasks.

        :param tasks: Tasks to run.
        :result: Finished tasks.
        """
        async with asyncio.TaskGroup() as task_group:
            return [task_group.create_task(task) for task in tasks]


class AsyncProcess(multiprocessing.Process):
    """Multiprocessing Process class whose target is an async function."""

    _target: t.Optional[t.Callable[..., t.Union[t.Any, t.Coroutine]]]
    _args: t.List[t.Any]
    _kwargs: t.Dict[str, t.Any]

    def run(self) -> None:
        if self._target:
            result_or_task = self._target(*self._args, **self._kwargs)

            asyncio.run(result_or_task) if is_async(self._target) else result_or_task
