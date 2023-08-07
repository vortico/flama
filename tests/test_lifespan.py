from unittest.mock import MagicMock, call, patch

import anyio.abc
import pytest

from flama import Flama
from flama.events import Events
from flama.lifespan import Context, Lifespan


class TestCaseContext:
    @pytest.fixture
    def lifespan(self):
        mock = MagicMock()
        mock.return_value = mock
        return mock

    @pytest.fixture
    def app(self):
        mock = MagicMock(Flama)
        mock.events = Events()
        return mock

    async def test_context(self, app, lifespan):
        def foo_handler():
            ...

        def bar_handler():
            ...

        app.events.register("startup", foo_handler)
        app.events.register("shutdown", bar_handler)

        context = Context(app, lifespan)
        assert context.app == app
        assert context.lifespan == lifespan
        assert lifespan.call_args_list == [call(app)]

        tg_mock = MagicMock(anyio.abc.TaskGroup)
        tg_mock.__aenter__.return_value = tg_mock
        with patch("flama.lifespan.anyio.create_task_group", return_value=tg_mock):
            async with context:
                assert lifespan.__aenter__.call_args_list == [call()]
                assert tg_mock.start_soon.call_args_list == [call(foo_handler)]

        assert tg_mock.start_soon.call_args_list == [call(foo_handler), call(bar_handler)]
        assert lifespan.__aexit__.call_args_list == [call(None, None, None)]


class TestCaseLifespan:
    @pytest.fixture
    def app(self):
        return MagicMock(Flama)

    @pytest.fixture
    def lifespan(self):
        return Lifespan(MagicMock())

    @pytest.mark.parametrize(
        ["context_side_effect", "receive_side_effect", "send_calls", "exception"],
        (
            pytest.param(
                [None],
                [None, None],
                [call({"type": "lifespan.startup.complete"}), call({"type": "lifespan.shutdown.complete"})],
                None,
                id="ok",
            ),
            pytest.param(
                [Exception("Foo")],
                [None, None],
                [call({"type": "lifespan.startup.failed", "message": "Foo"})],
                Exception("Foo"),
                id="fail_before_start",
            ),
            pytest.param(
                [None],
                [None, Exception("Foo")],
                [
                    call({"type": "lifespan.startup.complete"}),
                    call({"type": "lifespan.shutdown.failed", "message": "Foo"}),
                ],
                Exception("Foo"),
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
        context_side_effect,
        receive_side_effect,
        send_calls,
        exception,
    ):
        asgi_scope["app"] = app
        asgi_receive.side_effect = receive_side_effect

        context_mock = MagicMock(spec=Context)
        context_mock.return_value = context_mock
        context_mock.__aenter__.side_effect = context_side_effect
        with exception, patch("flama.lifespan.Context", new=context_mock):
            await lifespan(asgi_scope, asgi_receive, asgi_send)

        assert context_mock.call_args_list == [call(app, lifespan.lifespan)]
        assert asgi_send.call_args_list == send_calls
