import logging
import typing as t

from flama import concurrency, exceptions, types

if t.TYPE_CHECKING:
    from flama import Flama

__all__ = ["Lifespan"]

logger = logging.getLogger(__name__)


class Lifespan(types.AppClass):
    def __init__(self, lifespan: t.Optional[t.Callable[[t.Optional["Flama"]], t.AsyncContextManager]] = None):
        """A class that handles the lifespan of an application.

        It is responsible for calling the startup and shutdown events and the user defined lifespan.

        :param lifespan: A user defined lifespan. It must be a callable that returns an async context manager.
        """
        self.lifespan = lifespan

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Handles a lifespan request by initialising and finalising all modules and running a user defined lifespan.

        :param scope: ASGI request.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        app = scope["app"]
        message = await receive()
        if message["type"] == "lifespan.startup":
            try:
                logger.info("Application starting")
                app._status = types.AppStatus.STARTING
                await self._startup(app)
                for route in app.routes:

                    async def child_receive() -> types.Message:
                        return message

                    await route(scope, child_receive, send)
                await send(types.Message({"type": "lifespan.startup.complete"}))
                app._status = types.AppStatus.READY
                logger.info("Application ready")
            except BaseException as e:
                logger.exception("Application start failed")
                app._status = types.AppStatus.FAILED
                await send(types.Message({"type": "lifespan.startup.failed", "message": str(e)}))
                raise exceptions.ApplicationError("Lifespan startup failed") from e
        elif message["type"] == "lifespan.shutdown":
            try:
                logger.info("Application shutting down")
                app._status = types.AppStatus.SHUTTING_DOWN
                for route in app.routes:

                    async def child_receive() -> types.Message:
                        return message

                    await route(scope, child_receive, send)
                await self._shutdown(app)
                await send(types.Message({"type": "lifespan.shutdown.complete"}))
                app._status = types.AppStatus.SHUT_DOWN
                logger.info("Application shut down")
                return
            except BaseException as e:
                await send(types.Message({"type": "lifespan.shutdown.failed", "message": str(e)}))
                app._status = types.AppStatus.FAILED
                logger.exception("Application shutdown failed")
                raise exceptions.ApplicationError("Lifespan shutdown failed") from e
        else:
            logger.warning("Unknown lifespan message received: %s", str(message))

    async def _startup(self, app: "Flama") -> None:
        await concurrency.run_task_group(*(f() for f in app.events.startup))
        if self.lifespan:
            await self.lifespan(app).__aenter__()

    async def _shutdown(self, app: "Flama") -> None:
        if self.lifespan:
            await self.lifespan(app).__aexit__(None, None, None)
        await concurrency.run_task_group(*(f() for f in app.events.shutdown))
