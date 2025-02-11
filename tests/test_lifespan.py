import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import Flama, exceptions, types
from flama.lifespan import Lifespan


class TestCaseLifespan:
    @pytest.fixture
    def app(self):
        return MagicMock(Flama)

    @pytest.fixture
    def lifespan(self):
        return Lifespan(MagicMock())

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
        ["child_lifespan"],
        (
            pytest.param(MagicMock(), id="lifespan"),
            pytest.param(None, id="no_lifespan"),
        ),
    )
    async def test_startup(self, app, lifespan, child_lifespan):
        lifespan.lifespan = child_lifespan
        foo = AsyncMock()
        app.events = MagicMock()
        app.events.startup = [foo]

        await lifespan._startup(app)

        assert foo.await_args_list == [call()]
        if child_lifespan:
            assert lifespan.lifespan(app).__aenter__.await_args_list == [call()]

    @pytest.mark.parametrize(
        ["child_lifespan"],
        (
            pytest.param(MagicMock(), id="lifespan"),
            pytest.param(None, id="no_lifespan"),
        ),
    )
    async def test_shutdown(self, app, lifespan, child_lifespan):
        lifespan.lifespan = child_lifespan
        foo = AsyncMock()
        app.events = MagicMock()
        app.events.shutdown = [foo]

        await lifespan._shutdown(app)

        assert foo.await_args_list == [call()]
        if child_lifespan:
            assert lifespan.lifespan(app).__aexit__.await_args_list == [call(None, None, None)]
