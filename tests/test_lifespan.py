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
        ["startup_side_effect", "shutdown_side_effect", "send_calls", "app_status", "exception"],
        (
            pytest.param(
                None,
                None,
                [
                    call({"type": "lifespan.startup.complete"}),
                    call({"type": "lifespan.shutdown.complete"}),
                ],
                types.AppStatus.SHUT_DOWN,
                None,
                id="ok",
            ),
            pytest.param(
                Exception("Foo"),
                None,
                [
                    call({"type": "lifespan.startup.failed", "message": "Foo"}),
                ],
                types.AppStatus.FAILED,
                exceptions.ApplicationError("Lifespan startup failed"),
                id="fail_before_start",
            ),
            pytest.param(
                None,
                Exception("Foo"),
                [
                    call({"type": "lifespan.startup.complete"}),
                    call({"type": "lifespan.shutdown.failed", "message": "Foo"}),
                ],
                types.AppStatus.FAILED,
                exceptions.ApplicationError("Lifespan shutdown failed"),
                id="fail_after_start",
            ),
        ),
        indirect=["exception"],
    )
    async def test_call(
        self,
        app,
        lifespan,
        asgi_scope,
        asgi_receive,
        asgi_send,
        startup_side_effect,
        shutdown_side_effect,
        send_calls,
        app_status,
        exception,
    ):
        asgi_scope["app"] = app
        asgi_receive.side_effect = [
            types.Message({"type": "lifespan.startup"}),
            types.Message({"type": "http"}),
            types.Message({"type": "lifespan.shutdown"}),
        ]
        with exception, patch.object(lifespan, "_startup", side_effect=startup_side_effect), patch.object(
            lifespan, "_shutdown", side_effect=shutdown_side_effect
        ):
            await lifespan(asgi_scope, asgi_receive, asgi_send)

        assert asgi_send.call_args_list == send_calls
        assert app._status == app_status

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
