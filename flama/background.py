import asyncio
import enum
import functools
import sys
import typing as t
from multiprocessing import Process

import starlette.background

from flama import concurrency

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import ParamSpec

    t.ParamSpec = ParamSpec

__all__ = ["BackgroundTask", "BackgroundTasks", "Concurrency", "BackgroundThreadTask", "BackgroundProcessTask"]

P = t.ParamSpec("P")


class Concurrency(enum.Enum):
    thread = "thread"
    process = "process"


class BackgroundTask(starlette.background.BackgroundTask):
    def __init__(
        self, concurrency: t.Union[Concurrency, str], func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        self.func = self._create_task_function(func)
        self.args = args
        self.kwargs = kwargs
        self.concurrency = Concurrency(concurrency)

    def _create_task_function(self, func: t.Callable[P, t.Any]) -> t.Callable[P, t.Any]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def _inner(*args, **kwargs):
                await func(*args, **kwargs)

        else:

            @functools.wraps(func)
            async def _inner(*args, **kwargs):
                await concurrency.run(func, *args, **kwargs)

        return _inner

    def _create_process_target(self, func: t.Callable[P, t.Any]):
        @functools.wraps(func)
        def process_target(*args: P.args, **kwargs: P.kwargs):  # pragma: no cover
            policy = asyncio.get_event_loop_policy()
            loop = policy.new_event_loop()
            policy.set_event_loop(loop)
            loop.run_until_complete(func(*args, **kwargs))

        return process_target

    async def __call__(self):
        if self.concurrency == Concurrency.process:
            Process(target=self._create_process_target(self.func), args=self.args, kwargs=self.kwargs).start()
        else:
            await self.func(*self.args, **self.kwargs)


class BackgroundTasks(BackgroundTask):
    def __init__(self, tasks: t.Optional[t.Sequence[BackgroundTask]] = None):
        self.tasks = list(tasks) if tasks else []

    def add_task(
        self, concurrency: t.Union[Concurrency, str], func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        task = BackgroundTask(concurrency, func, *args, **kwargs)
        self.tasks.append(task)

    async def __call__(self) -> None:
        for task in self.tasks:
            await task()


class BackgroundThreadTask(BackgroundTask):
    def __init__(self, func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs):
        super().__init__(Concurrency.thread, func, *args, **kwargs)


class BackgroundProcessTask(BackgroundTask):
    def __init__(self, func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs):
        super().__init__(Concurrency.process, func, *args, **kwargs)
