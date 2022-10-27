import sys
from unittest.mock import PropertyMock, call, patch

import pytest

from flama import http
from flama.debug.middleware import ExceptionMiddleware, ServerErrorMiddleware
from flama.middleware import Middleware, MiddlewareStack

if sys.version_info >= (3, 8):  # PORT: Remove when stop supporting 3.7 # pragma: no cover
    from unittest.mock import AsyncMock
else:  # pragma: no cover
    from asyncmock import AsyncMock


class TestCaseMiddlewareStack:
    @pytest.fixture
    def middleware(self):
        class FooMiddleware:
            def __init__(self, *args, **kwargs):
                ...

            def __call__(self, *args, **kwargs):
                return None

        return Middleware(FooMiddleware)

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
        def handler(request: http.Request, exc: Exception) -> http.Response:
            ...

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

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    async def test_call(self, stack, asgi_scope, asgi_receive, asgi_send):
        with patch.object(MiddlewareStack, "stack", new=PropertyMock(return_value=AsyncMock())):
            await stack(asgi_scope, asgi_receive, asgi_send)
            assert stack.stack.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]
