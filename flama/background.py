import enum
import functools
import sys
import typing as t

import starlette.background

from flama import concurrency

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import ParamSpec

    t.ParamSpec = ParamSpec  # type: ignore

if sys.version_info < (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover

    class StrEnum(str, enum.Enum):
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

    enum.StrEnum = StrEnum  # type: ignore


__all__ = ["BackgroundTask", "BackgroundTasks", "Concurrency", "BackgroundThreadTask", "BackgroundProcessTask"]

P = t.ParamSpec("P")  # type: ignore # PORT: Remove this comment when stop supporting 3.9


class task_wrapper:
    def __init__(self, target: t.Callable[P, t.Union[None, t.Awaitable[None]]]):
        self.target = target
        functools.update_wrapper(self, target)

    async def __call__(self, *args, **kwargs):
        await concurrency.run(self.target, *args, **kwargs)


class Concurrency(enum.StrEnum):  # type: ignore # PORT: Remove this comment when stop supporting 3.10
    thread = enum.auto()
    process = enum.auto()


class BackgroundTask(starlette.background.BackgroundTask):
    def __init__(
        self,
        concurrency: t.Union[Concurrency, str],
        func: t.Callable[P, t.Union[None, t.Awaitable[None]]],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> None:
        self.func = task_wrapper(func)
        self.args = args
        self.kwargs = kwargs
        self.concurrency = Concurrency[concurrency]

    async def __call__(self):
        if self.concurrency == Concurrency.process:
            concurrency.AsyncProcess(target=self.func, args=self.args, kwargs=self.kwargs).start()
        else:
            await self.func(*self.args, **self.kwargs)


class BackgroundTasks(BackgroundTask):
    def __init__(self, tasks: t.Optional[t.Sequence[BackgroundTask]] = None):
        self.tasks = list(tasks) if tasks else []

    def add_task(
        self, concurrency: t.Union[Concurrency, str], func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        self.tasks.append(BackgroundTask(concurrency, func, *args, **kwargs))

    async def __call__(self) -> None:
        for task in self.tasks:
            await task()


class BackgroundThreadTask(BackgroundTask):
    def __init__(self, func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs):
        super().__init__(Concurrency.thread, func, *args, **kwargs)


class BackgroundProcessTask(BackgroundTask):
    def __init__(self, func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs):
        super().__init__(Concurrency.process, func, *args, **kwargs)
