import typing

import anyio

if typing.TYPE_CHECKING:
    from flama import Flama


class Lifespan:
    def __init__(self, app: "Flama", lifespan: typing.Callable[["Flama"], typing.AsyncContextManager] = None):
        self.app = app
        self.lifespan = lifespan

    async def __aenter__(self):
        async with anyio.create_task_group() as tg:
            for module in self.app.modules.values():
                tg.start_soon(module.on_startup)

        if self.lifespan:  # pragma: no cover
            await self.lifespan.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.lifespan:  # pragma: no cover
            await self.lifespan.__aexit__(exc_type, exc_val, exc_tb)

        async with anyio.create_task_group() as tg:
            for module in self.app.modules.values():
                tg.start_soon(module.on_shutdown)

    def __call__(self, app: object) -> "Lifespan":
        return self
