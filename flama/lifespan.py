import contextlib
import typing as t

import anyio

from flama import types

if t.TYPE_CHECKING:
    from flama import Flama

__all__ = ["Lifespan"]


class Context(t.AsyncContextManager):
    def __init__(
        self,
        app: "Flama",
        lifespan: t.Optional[t.Callable[[t.Optional["Flama"]], t.AsyncContextManager]] = None,
    ):
        self.app = app
        self.lifespan = lifespan(app) if lifespan else contextlib.AsyncExitStack()

    async def __aenter__(self) -> None:
        async with anyio.create_task_group() as tg:
            for handler in self.app.events.startup:
                tg.start_soon(handler)

        await self.lifespan.__aenter__()

    async def __aexit__(
        self, exc_type: t.Optional[t.Type[BaseException]], exc_val: t.Optional[BaseException], exc_tb
    ) -> None:
        await self.lifespan.__aexit__(exc_type, exc_val, exc_tb)

        async with anyio.create_task_group() as tg:
            for handler in self.app.events.shutdown:
                tg.start_soon(handler)


class Lifespan(types.AppClass):
    def __init__(self, lifespan: t.Optional[t.Callable[[t.Optional["Flama"]], t.AsyncContextManager]] = None):
        self.lifespan = lifespan

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Handles a lifespan request by initializing all mo

        :param scope: ASGI request.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        started = False
        await receive()
        try:
            async with Context(scope["app"], self.lifespan):
                await send(types.Message({"type": "lifespan.startup.complete"}))
                started = True
                await receive()
        except BaseException as e:
            await send(
                types.Message(
                    {"type": "lifespan.shutdown.failed" if started else "lifespan.startup.failed", "message": str(e)}
                )
            )
            raise
        else:
            await send(types.Message({"type": "lifespan.shutdown.complete"}))
