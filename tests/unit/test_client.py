import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import Flama, types
from flama.client import Client, LifespanContextManager
from flama.models.modules import ModelsModule


@pytest.fixture(scope="function")
def app():
    app_mock = AsyncMock(spec=Flama)
    app_mock.models = MagicMock(spec=ModelsModule)
    return app_mock


class TestCaseLifespanContextManager:
    @pytest.fixture(scope="function")
    def lifespan_context_manager(self, app) -> LifespanContextManager:
        return LifespanContextManager(app=app)

    @pytest.mark.parametrize(
        ["exception"],
        (
            pytest.param(None, id="ok"),
            pytest.param(Exception("foo"), id="exception"),
        ),
        indirect=["exception"],
    )
    async def test_startup(self, exception, lifespan_context_manager):
        lifespan_context_manager._exception = exception.exception
        lifespan_context_manager._startup_complete = MagicMock(spec=asyncio.Event)
        with exception:
            await lifespan_context_manager._startup()
            assert lifespan_context_manager._startup_complete.wait.await_args_list == [call()]

    async def test_shutdown(self, lifespan_context_manager):
        lifespan_context_manager._shutdown_complete = MagicMock(spec=asyncio.Event)
        await lifespan_context_manager._shutdown()
        assert lifespan_context_manager._shutdown_complete.wait.await_args_list == [call()]

    async def test_receive(self, lifespan_context_manager):
        lifespan_context_manager._receive_queue.get = AsyncMock()

        await lifespan_context_manager._receive()

        assert lifespan_context_manager._receive_queue.get.await_args_list == [call()]

    @pytest.mark.parametrize(
        ["message", "startup", "shutdown"],
        (
            pytest.param(types.Message({"type": "lifespan.startup.complete"}), True, False, id="startup"),
            pytest.param(types.Message({"type": "lifespan.shutdown.complete"}), False, True, id="shutdown"),
            pytest.param(types.Message({"type": "foo"}), False, False, id="otherwise"),
        ),
    )
    async def test_send(self, message, startup, shutdown, lifespan_context_manager):
        expected_startup = [call()] if startup else []
        expected_shutdown = [call()] if shutdown else []

        lifespan_context_manager._startup_complete.set = MagicMock()
        lifespan_context_manager._shutdown_complete.set = MagicMock()

        await lifespan_context_manager._send(message)

        assert lifespan_context_manager._startup_complete.set.call_args_list == expected_startup
        assert lifespan_context_manager._shutdown_complete.set.call_args_list == expected_shutdown

    @pytest.mark.parametrize(
        ["exception"],
        (
            pytest.param(None, id="ok"),
            pytest.param(Exception("foo"), id="exception"),
        ),
        indirect=["exception"],
    )
    async def test_app_task(self, exception, lifespan_context_manager):
        lifespan_context_manager._startup_complete.set = MagicMock()
        lifespan_context_manager._shutdown_complete.set = MagicMock()

        if exception:
            lifespan_context_manager.app.side_effect = exception.exception

        with exception:
            await lifespan_context_manager._app_task()
            assert lifespan_context_manager.app.await_args_list == [
                call(
                    types.Scope({"type": "lifespan"}), lifespan_context_manager._receive, lifespan_context_manager._send
                )
            ]

        if exception:
            assert lifespan_context_manager._exception == exception.exception
            assert lifespan_context_manager._startup_complete.set.call_args_list == [call()]
            assert lifespan_context_manager._shutdown_complete.set.call_args_list == [call()]

    @pytest.mark.parametrize(
        ["startup_mock", "shutdown_mock", "exception"],
        (
            pytest.param(
                AsyncMock(),
                AsyncMock(),
                None,
                id="ok",
            ),
            pytest.param(
                AsyncMock(side_effect=Exception("foo")),
                AsyncMock(),
                Exception("foo"),
                id="startup_exception",
            ),
            pytest.param(
                AsyncMock(),
                AsyncMock(side_effect=Exception("foo")),
                Exception("foo"),
                id="shutdown_exception",
            ),
        ),
        indirect=["exception"],
    )
    async def test_context(self, lifespan_context_manager, startup_mock, shutdown_mock, exception):
        with (
            exception,
            patch.object(lifespan_context_manager, "_app_task"),
            patch.object(lifespan_context_manager, "_startup", startup_mock),
            patch.object(lifespan_context_manager, "_shutdown", shutdown_mock),
        ):
            async with lifespan_context_manager:
                assert lifespan_context_manager._app_task.call_args_list == [call()]
                assert lifespan_context_manager._startup.await_args_list == [call()]

                if exception:
                    assert lifespan_context_manager._stop_app.await_args_list == [call()]

            assert lifespan_context_manager._app_task.call_args_list == [call(), call()]
            assert lifespan_context_manager._shutdown.await_args_list == [call()]


class TestCaseClient:
    def test_init_models(self, app):
        with patch("flama.client.Flama", return_value=app), patch("importlib.metadata.version", return_value="x.y.z"):
            client = Client(models=[("foo", "/foo/", "model_foo.flm"), ("bar", "/bar/", "model_bar.flm")])

        assert client.app == app
        assert client.lifespan
        assert client.lifespan.app == app
        assert client.models == {"foo": "/foo/", "bar": "/bar/"}
        assert app.models.add_model.call_args_list == [
            call("/foo/", "model_foo.flm", "foo"),
            call("/bar/", "model_bar.flm", "bar"),
        ]

    def test_init_no_app(self):
        with patch("importlib.metadata.version", return_value="x.y.z"):
            client = Client()

        assert client.lifespan is None

    async def test_context_app(self, app):
        client = Client(app=app)
        client.lifespan = MagicMock(spec=LifespanContextManager)

        with patch("httpx.AsyncClient.__aenter__") as aenter_mock, patch("httpx.AsyncClient.__aexit__") as aexit_mock:
            async with client:
                assert aenter_mock.await_args_list == [call()]
                assert client.lifespan.__aenter__.await_args_list == [call()]

            assert client.lifespan.__aexit__.await_args_list == [call(None, None, None)]
            assert aexit_mock.await_args_list == [call(None, None, None)]

    async def test_context_no_app(self):
        client = Client()

        with patch("httpx.AsyncClient.__aenter__") as aenter_mock, patch("httpx.AsyncClient.__aexit__") as aexit_mock:
            async with client:
                assert aenter_mock.await_args_list == [call()]

            assert aexit_mock.await_args_list == [call(None, None, None)]

    async def test_model_request(self, app):
        with (
            patch("flama.client.Flama", return_value=app),
            patch("builtins.super"),
            patch("importlib.metadata.version", return_value="x.y.z"),
        ):
            client = Client(models=[("foo", "/foo/", "model_foo.flm")])

        with patch.object(client, "request") as request_mock:
            await client.model_request("foo", "GET", "/")

            assert request_mock.call_args_list == [call("GET", "/foo/")]
