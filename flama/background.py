import functools
import typing as t

from flama import concurrency, exceptions

__all__ = ["BackgroundTask", "BackgroundTasks", "BackgroundThreadTask", "BackgroundProcessTask"]

P = t.ParamSpec("P")


class task_wrapper:
    def __init__(self, target: t.Callable[P, None | t.Awaitable[None]]):
        self.target = target
        functools.update_wrapper(self, target)

    async def __call__(self, *args, **kwargs):
        await concurrency.run(self.target, *args, **kwargs)


Concurrency = t.Literal["thread", "process"]


class BackgroundTask:
    def __init__(
        self, concurrency: Concurrency, func: t.Callable[P, None | t.Awaitable[None]], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        if concurrency not in ("thread", "process"):
            raise exceptions.ApplicationError("Wrong concurrency mode")

        self.func = task_wrapper(func)
        self.args = args
        self.kwargs = kwargs
        self.concurrency = concurrency

    async def __call__(self):
        if self.concurrency == "process":
            concurrency.AsyncProcess(target=self.func, args=self.args, kwargs=self.kwargs).start()
        else:
            await self.func(*self.args, **self.kwargs)


class BackgroundTasks(BackgroundTask):
    def __init__(self, tasks: t.Sequence[BackgroundTask] | None = None):
        self.tasks = list(tasks) if tasks else []

    def add_task(self, concurrency: Concurrency, func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs) -> None:
        self.tasks.append(BackgroundTask(concurrency, func, *args, **kwargs))

    async def __call__(self) -> None:
        for task in self.tasks:
            await task()


class BackgroundThreadTask(BackgroundTask):
    def __init__(self, func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs):
        super().__init__("thread", func, *args, **kwargs)


class BackgroundProcessTask(BackgroundTask):
    def __init__(self, func: t.Callable[P, t.Any], *args: P.args, **kwargs: P.kwargs):
        super().__init__("process", func, *args, **kwargs)
