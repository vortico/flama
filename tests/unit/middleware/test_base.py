from unittest.mock import AsyncMock, PropertyMock, call, patch

import pytest

from flama import Flama
from flama.debug.middleware import ExceptionMiddleware, ServerErrorMiddleware
from flama.middleware import Middleware, MiddlewareStack


class TestCaseMiddleware:
    def test_build(self):
        class FooMiddleware(Middleware):
            def __init__(self, x=1):
                self.x = x

        m = FooMiddleware(x=42)
        app = AsyncMock()
        result = m._build(app)

        assert result is m
        assert m.app is app
        assert m.x == 42

    async def test_default_call(self):
        m = Middleware()
        app = AsyncMock()
        m._build(app)
        scope, receive, send = AsyncMock(), AsyncMock(), AsyncMock()

        await m(scope, receive, send)

        assert app.call_count == 1


class TestCaseMiddlewareStack:
    @pytest.fixture
    def middleware(self):
        class FooMiddleware(Middleware):
            async def __call__(self, scope, receive, send):
                return None

        return FooMiddleware()

    @pytest.fixture
    def app(self):
        return AsyncMock()

    @pytest.fixture
    def stack(self, app, middleware):
        return MiddlewareStack(app=app, middleware=[], debug=True)

    def test_init(self, app, middleware):
        stack = MiddlewareStack(app=app, middleware=[middleware], debug=True)

        assert stack.app == app
        assert stack.middleware == [middleware]
        assert stack.debug
        assert stack._exception_handlers == {}

    def test_stack(self, stack):
        assert stack._stack is None
        assert stack.stack
        assert isinstance(stack._stack, ServerErrorMiddleware)
        assert isinstance(stack._stack.app, ExceptionMiddleware)

    def test_add_exception_handler(self, stack):
        def handler(scope, receive, send, exc): ...

        assert stack._stack is None
        assert stack.stack
        assert stack._stack is not None

        stack.add_exception_handler(400, handler)
        stack.add_exception_handler(ValueError, handler)

        assert stack._stack is None
        assert stack._exception_handlers == {400: handler, ValueError: handler}

    def test_add_middleware(self, stack, middleware):
        assert stack._stack is None
        assert stack.stack
        assert stack._stack is not None

        stack.add_middleware(middleware)

        assert stack._stack is None
        assert stack.middleware == [middleware]

    async def test_call(self, stack, asgi_scope, asgi_receive, asgi_send):
        with patch.object(MiddlewareStack, "stack", new=PropertyMock(return_value=AsyncMock())):
            await stack(asgi_scope, asgi_receive, asgi_send)
            assert stack.stack.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    async def test_on_startup(self, stack):
        _ = stack.stack
        started = []

        class StartupMiddleware(Middleware):
            async def on_startup(self):
                started.append(True)

        instance = StartupMiddleware()
        stack._instances.append(instance)

        await stack.on_startup()

        assert started == [True]

    async def test_on_shutdown(self, stack):
        _ = stack.stack
        stopped = []

        class ShutdownMiddleware(Middleware):
            async def on_shutdown(self):
                stopped.append(True)

        instance = ShutdownMiddleware()
        stack._instances.append(instance)

        await stack.on_shutdown()

        assert stopped == [True]


class TestCaseMiddlewareStackIntegration:
    @pytest.fixture(scope="function")
    def app(self):
        class LifecycleMiddleware(Middleware):
            started = False
            stopped = False

            async def on_startup(self):
                LifecycleMiddleware.started = True

            async def on_shutdown(self):
                LifecycleMiddleware.stopped = True

        return Flama(schema=None, docs=None, middleware=[LifecycleMiddleware()])

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/ping/")
        def ping():
            return {"pong": True}

    @pytest.mark.parametrize(
        ["path", "method", "status_code", "body"],
        [
            pytest.param("/ping/", "get", 200, {"pong": True}, id="simple_request"),
        ],
    )
    async def test_request(self, client, path, method, status_code, body):
        response = await client.request(method, path)

        assert response.status_code == status_code
        assert response.json() == body
