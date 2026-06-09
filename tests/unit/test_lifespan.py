import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import Flama, Module, exceptions, types
from flama.client import LifespanContextManager
from flama.lifespan import Lifespan


class TestCaseLifespan:
    @pytest.fixture(scope="function")
    def app(self):
        return MagicMock(Flama)

    @pytest.fixture(scope="function")
    def lifespan(self):
        return Lifespan(MagicMock())

    @pytest.fixture(scope="function")
    def ordering_app(self):
        order: list[str] = []

        class SlowModule(Module):
            name = "slow_module"

            async def on_startup(self):
                await asyncio.sleep(0.01)
                order.append("module_startup")

            async def on_shutdown(self):
                order.append("module_shutdown")

        app = Flama(docs=None, schema=None, modules=[SlowModule()])

        @app.on_event("startup")
        async def user_startup():
            order.append("user_startup")

        @app.on_event("shutdown")
        async def user_shutdown():
            await asyncio.sleep(0.01)
            order.append("user_shutdown")

        return app, order

    @pytest.mark.parametrize(
        ["states", "startup_side_effect", "shutdown_side_effect", "exception"],
        (
            pytest.param(
                (
                    (
                        [],
                        [],
                        types.AppStatus.NOT_STARTED,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.startup"}),
                        ],
                        [
                            types.Message({"type": "lifespan.startup.complete"}),
                        ],
                        types.AppStatus.READY,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.shutdown"}),
                        ],
                        [
                            types.Message({"type": "lifespan.shutdown.complete"}),
                        ],
                        types.AppStatus.SHUT_DOWN,
                    ),
                ),
                None,
                None,
                None,
                id="ok",
            ),
            pytest.param(
                (
                    (
                        [],
                        [],
                        types.AppStatus.NOT_STARTED,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.startup"}),
                        ],
                        [
                            types.Message({"type": "lifespan.startup.complete"}),
                        ],
                        types.AppStatus.READY,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.shutdown"}),
                        ],
                        [
                            types.Message({"type": "lifespan.shutdown.complete"}),
                        ],
                        types.AppStatus.SHUT_DOWN,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.startup"}),
                        ],
                        [
                            types.Message({"type": "lifespan.startup.complete"}),
                        ],
                        types.AppStatus.READY,
                    ),
                ),
                None,
                None,
                None,
                id="restart",
            ),
            pytest.param(
                (
                    (
                        [],
                        [],
                        types.AppStatus.NOT_STARTED,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.startup"}),
                        ],
                        [
                            types.Message({"type": "lifespan.startup.failed", "message": "Foo"}),
                        ],
                        types.AppStatus.FAILED,
                    ),
                ),
                Exception("Foo"),
                None,
                exceptions.ApplicationError("Lifespan startup failed"),
                id="startup_fail",
            ),
            pytest.param(
                (
                    (
                        [],
                        [],
                        types.AppStatus.NOT_STARTED,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.startup"}),
                        ],
                        [
                            types.Message({"type": "lifespan.startup.complete"}),
                        ],
                        types.AppStatus.READY,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.shutdown"}),
                        ],
                        [
                            types.Message({"type": "lifespan.shutdown.failed", "message": "Foo"}),
                        ],
                        types.AppStatus.FAILED,
                    ),
                ),
                None,
                Exception("Foo"),
                exceptions.ApplicationError("Lifespan shutdown failed"),
                id="shutdown_fail",
            ),
            pytest.param(
                (
                    (
                        [],
                        [],
                        types.AppStatus.NOT_STARTED,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.startup"}),
                        ],
                        [
                            types.Message({"type": "lifespan.startup.complete"}),
                        ],
                        types.AppStatus.READY,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.startup"}),
                        ],
                        [
                            types.Message(
                                {
                                    "type": "lifespan.startup.failed",
                                    "message": "Trying to start application from 'AppStatus.READY' state",
                                }
                            ),
                        ],
                        types.AppStatus.READY,
                    ),
                ),
                None,
                None,
                exceptions.ApplicationError("Trying to start application from 'AppStatus.READY' state"),
                id="start_from_ready",
            ),
            pytest.param(
                (
                    (
                        [],
                        [],
                        types.AppStatus.NOT_STARTED,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.shutdown"}),
                        ],
                        [
                            types.Message(
                                {
                                    "type": "lifespan.shutdown.failed",
                                    "message": "Trying to shutdown application from 'AppStatus.NOT_STARTED' state",
                                }
                            ),
                        ],
                        types.AppStatus.READY,
                    ),
                ),
                None,
                None,
                exceptions.ApplicationError("Trying to shutdown application from 'AppStatus.NOT_STARTED' state"),
                id="shutdown_from_not_started",
            ),
            pytest.param(
                (
                    (
                        [],
                        [],
                        types.AppStatus.NOT_STARTED,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.startup"}),
                        ],
                        [
                            types.Message({"type": "lifespan.startup.complete"}),
                        ],
                        types.AppStatus.READY,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.shutdown"}),
                        ],
                        [
                            types.Message({"type": "lifespan.shutdown.complete"}),
                        ],
                        types.AppStatus.SHUT_DOWN,
                    ),
                    (
                        [
                            types.Message({"type": "lifespan.shutdown"}),
                        ],
                        [
                            types.Message(
                                {
                                    "type": "lifespan.shutdown.failed",
                                    "message": "Trying to shutdown application from 'AppStatus.SHUT_DOWN' state",
                                }
                            ),
                        ],
                        types.AppStatus.SHUT_DOWN,
                    ),
                ),
                None,
                None,
                exceptions.ApplicationError("Trying to shutdown application from 'AppStatus.SHUT_DOWN' state"),
                id="shutdown_from_shutdown",
            ),
            pytest.param(
                (
                    (
                        [
                            types.Message({"type": "lifespan.unknown"}),
                        ],
                        [],
                        types.AppStatus.NOT_STARTED,
                    ),
                ),
                None,
                None,
                None,
                id="unknown_message",
            ),
        ),
        indirect=["exception"],
    )
    async def test_call(self, states, startup_side_effect, shutdown_side_effect, exception):
        receive_queue = asyncio.Queue()
        send_queue = asyncio.Queue()

        async def receive() -> types.Message:
            return await receive_queue.get()

        async def send(message: types.Message) -> None:
            await send_queue.put(message)

        app = Flama(docs=None, schema=None)
        sub_app = Flama(docs=None, schema=None)
        app.mount("/foo", sub_app)

        lifespan = app.router.lifespan

        with (
            exception,
            patch.object(lifespan, "_startup", side_effect=startup_side_effect),
            patch.object(lifespan, "_shutdown", side_effect=shutdown_side_effect),
        ):
            for receive_messages, send_messages, app_status in states:
                for m in receive_messages:
                    await receive_queue.put(m)
                    await lifespan(types.Scope({"app": app, "type": "lifespan"}), receive, send)

                assert [await send_queue.get() for _ in range(len(send_messages))] == send_messages
                assert app._status == app_status
                assert sub_app._status == app_status

    @pytest.mark.parametrize(
        ["child_lifespan", "has_events"],
        (
            pytest.param(MagicMock(), True, id="lifespan_with_events"),
            pytest.param(None, True, id="no_lifespan_with_events"),
            pytest.param(None, False, id="no_lifespan_no_events"),
        ),
    )
    async def test_startup(self, app, lifespan, child_lifespan, has_events):
        lifespan.lifespan = child_lifespan
        foo = AsyncMock()
        app.events = MagicMock()
        app.events.startup = [foo] if has_events else []
        app.modules = MagicMock()
        app.modules.on_startup = AsyncMock()
        app.middleware = MagicMock()
        app.middleware.on_startup = AsyncMock()

        await lifespan._startup(app)

        # Framework lifecycle (modules then middleware) is initialised as a barrier before user handlers.
        assert app.modules.on_startup.await_args_list == [call()]
        assert app.middleware.on_startup.await_args_list == [call()]
        if has_events:
            assert foo.await_args_list == [call()]
        if child_lifespan:
            # The entered context manager is stored and __aenter__ is awaited exactly once.
            assert lifespan._context is lifespan.lifespan.return_value
            assert lifespan._context.__aenter__.await_args_list == [call()]

    @pytest.mark.parametrize(
        ["child_lifespan", "has_events"],
        (
            pytest.param(MagicMock(), True, id="lifespan_with_events"),
            pytest.param(None, True, id="no_lifespan_with_events"),
            pytest.param(None, False, id="no_lifespan_no_events"),
        ),
    )
    async def test_shutdown(self, app, lifespan, child_lifespan, has_events):
        lifespan.lifespan = child_lifespan
        # Shutdown exits the context manager entered at startup, so simulate that prior state.
        context = lifespan.lifespan(app) if child_lifespan else None
        lifespan._context = context
        foo = AsyncMock()
        app.events = MagicMock()
        app.events.shutdown = [foo] if has_events else []
        app.modules = MagicMock()
        app.modules.on_shutdown = AsyncMock()
        app.middleware = MagicMock()
        app.middleware.on_shutdown = AsyncMock()

        await lifespan._shutdown(app)

        if has_events:
            assert foo.await_args_list == [call()]
        if child_lifespan:
            assert context.__aexit__.await_args_list == [call(None, None, None)]
            assert lifespan._context is None
        # Framework lifecycle is torn down last and in reverse order (middleware then modules).
        assert app.middleware.on_shutdown.await_args_list == [call()]
        assert app.modules.on_shutdown.await_args_list == [call()]

    async def test_asynccontextmanager_lifespan_enter_exit_same_instance(self):
        """A ``@contextlib.asynccontextmanager`` lifespan must be entered and exited exactly once.

        Regression: startup and shutdown used to call the lifespan factory twice (entering one
        instance and exiting a different one), which re-ran the generator on exit and raised
        ``RuntimeError: generator didn't stop``.
        """
        events = []

        @contextlib.asynccontextmanager
        async def lifespan(app):
            events.append("startup")
            yield
            events.append("shutdown")

        app = Flama(docs=None, schema=None, lifespan=lifespan)

        async with LifespanContextManager(app):
            assert events == ["startup"]

        assert events == ["startup", "shutdown"]

    async def test_framework_startup_runs_before_user_handlers(self, ordering_app):
        """Modules (and middleware) must be fully initialised before user startup handlers run, and torn down after.

        Regression: framework and user lifecycle events used to share a single concurrent task group, so a user
        startup handler depending on a module (e.g. accessing the engine created by ``SQLAlchemyModule.on_startup``)
        could run before module init finished. The small sleeps in the fixture would let a racing counterpart win if
        the ordering were not enforced, making this a deterministic guard.
        """
        app, order = ordering_app

        async with LifespanContextManager(app):
            assert order.index("module_startup") < order.index("user_startup")

        assert order.index("user_shutdown") < order.index("module_shutdown")
