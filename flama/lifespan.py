import asyncio
import logging
import typing as t

from flama import concurrency, exceptions, types

__all__ = ["Lifespan"]

logger = logging.getLogger(__name__)


class Lifespan(types.ASGIAppClass):
    def __init__(self, lifespan: t.Callable[[types.App | None], t.AsyncContextManager] | None = None):
        """A class that handles the lifespan of an application.

        It is responsible for calling the startup and shutdown events and the user defined lifespan.

        :param lifespan: A user defined lifespan. It must be a callable that returns an async context manager.
        """
        self.lifespan = lifespan
        self.lock = asyncio.Lock()
        self._context: t.AsyncContextManager | None = None

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Handles a lifespan request by initialising and finalising all modules and running a user defined lifespan.

        :param scope: ASGI request.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        async with self.lock:
            app = scope["app"]
            message = await receive()
            logger.debug("Start lifespan for app '%s' from status '%s' with message '%s'", app, app.status, message)
            if message["type"] == "lifespan.startup":
                if app.status not in (types.AppStatus.NOT_STARTED, types.AppStatus.SHUT_DOWN):
                    msg = f"Trying to start application from '{app._status}' state"
                    await send(types.Message({"type": "lifespan.startup.failed", "message": msg}))
                    raise exceptions.ApplicationError(msg)

                try:
                    logger.info("Application starting")
                    app.status = types.AppStatus.STARTING
                    await self._startup(app)
                    await self._child_propagation(app, scope, message)
                    app.status = types.AppStatus.READY
                    await send(types.Message({"type": "lifespan.startup.complete"}))
                    logger.info("Application ready")
                except BaseException as e:
                    logger.exception("Application start failed")
                    app.status = types.AppStatus.FAILED
                    await send(types.Message({"type": "lifespan.startup.failed", "message": str(e)}))
                    raise exceptions.ApplicationError("Lifespan startup failed") from e
            elif message["type"] == "lifespan.shutdown":
                if app.status != types.AppStatus.READY:
                    msg = f"Trying to shutdown application from '{app._status}' state"
                    await send(types.Message({"type": "lifespan.shutdown.failed", "message": msg}))
                    raise exceptions.ApplicationError(msg)

                try:
                    logger.info("Application shutting down")
                    app.status = types.AppStatus.SHUTTING_DOWN
                    await self._child_propagation(app, scope, message)
                    await self._shutdown(app)
                    app.status = types.AppStatus.SHUT_DOWN
                    await send(types.Message({"type": "lifespan.shutdown.complete"}))
                    logger.info("Application shut down")
                except BaseException as e:
                    await send(types.Message({"type": "lifespan.shutdown.failed", "message": str(e)}))
                    app.status = types.AppStatus.FAILED
                    logger.exception("Application shutdown failed")
                    raise exceptions.ApplicationError("Lifespan shutdown failed") from e
            else:
                logger.warning("Unknown lifespan message received: %s", str(message))

            logger.debug("End lifespan for app '%s' with status '%s'", app, app.status)

    async def _startup(self, app: types.App) -> None:
        # Initialise the framework lifecycle first, as a barrier: modules then middleware. User startup handlers
        # (run concurrently below) and the user lifespan execute strictly afterwards, so they can rely on fully
        # initialised modules -- e.g. the engine created by ``SQLAlchemyModule.on_startup``. Running everything in a
        # single task group instead would race module init against user handlers.
        await app.modules.on_startup()
        await app.middleware.on_startup()

        if app.events.startup:
            await concurrency.run_task_group(*(f() for f in app.events.startup))

        if self.lifespan:
            # Keep a reference to the entered context manager so shutdown exits this very same
            # instance. Calling the lifespan factory again would create a fresh context manager and
            # break the canonical ``@contextlib.asynccontextmanager`` pattern (its generator would be
            # re-run from the start on exit).
            self._context = self.lifespan(app)
            await self._context.__aenter__()

    async def _shutdown(self, app: types.App) -> None:
        if self.lifespan and self._context is not None:
            context, self._context = self._context, None
            await context.__aexit__(None, None, None)

        if app.events.shutdown:
            await concurrency.run_task_group(*(f() for f in app.events.shutdown))

        # Tear down the framework lifecycle last and in reverse order (middleware then modules), mirroring startup.
        await app.middleware.on_shutdown()
        await app.modules.on_shutdown()

    async def _child_propagation(self, app: types.App, scope: types.Scope, message: types.Message) -> None:
        async def child_receive() -> types.Message:
            return message

        async def child_send(message: types.Message) -> None: ...

        if app.routes:
            await concurrency.run_task_group(
                *(route(types.Scope({**scope, "app": app}), child_receive, child_send) for route in app.routes)
            )
