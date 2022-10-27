import sys
from unittest.mock import MagicMock, call, patch

import pytest
from starlette.middleware import Middleware

from flama import Component, Flama, Module, Mount, Route, Router
from flama.applications import DEFAULT_MODULES
from flama.injection.components import Components
from flama.injection.injector import Injector
from flama.middleware import MiddlewareStack

if sys.version_info >= (3, 8):  # PORT: Remove when stop supporting 3.7 # pragma: no cover
    from unittest.mock import AsyncMock
else:  # pragma: no cover
    from asyncmock import AsyncMock


class TestCaseFlama:
    @pytest.fixture(scope="function")
    def component_mock(self):
        return MagicMock(spec=Component)

    @pytest.fixture(scope="function")
    def module_mock(self):
        class Foo(Module):
            name = "foo"

        return Foo

    def test_injector(self, app):
        assert isinstance(app.injector, Injector)

    def test_components(self, app):
        assert isinstance(app.components, Components)
        assert app.components == set()

    def test_recursion(self, component_mock, module_mock):
        root_app = Flama(schema=None, docs=None)
        root_app.add_get("/foo", lambda: {})

        assert len(root_app.router.routes) == 1
        assert root_app.router.main_app == root_app
        assert root_app.components == set()
        assert root_app.modules == DEFAULT_MODULES

        leaf_app = Flama(schema=None, docs=None, components={component_mock}, modules={module_mock})
        leaf_app.add_get("/bar", lambda: {})

        assert len(leaf_app.router.routes) == 1
        assert leaf_app.router.main_app == leaf_app
        assert leaf_app.components == [component_mock]
        assert leaf_app.modules == [*DEFAULT_MODULES, module_mock]

        root_app.mount("/app", app=leaf_app)

        assert len(root_app.router.routes) == 2
        # Check mount is initialized
        assert isinstance(root_app.routes[1], Mount)
        mount_route = root_app.router.routes[1]
        assert mount_route.path == "/app"
        # Check router is created and initialized
        assert isinstance(mount_route.app, Flama)
        mount_app = mount_route.app
        assert isinstance(mount_app.app, Router)
        mount_router = mount_app.app
        # Check main_app is propagated
        assert mount_router.main_app == root_app
        # Check components are collected across the entire tree
        assert mount_router.components == [component_mock]
        assert root_app.components == [component_mock]
        # Check modules are isolated for each app
        assert mount_app.modules == [*DEFAULT_MODULES, module_mock]
        assert root_app.modules == DEFAULT_MODULES

    def test_declarative_recursion(self, component_mock, module_mock):
        leaf_routes = [Route("/bar", lambda: {})]
        leaf_app = Flama(routes=leaf_routes, schema=None, docs=None, components={component_mock}, modules={module_mock})
        root_routes = [Route("/foo", lambda: {}), Mount("/app", app=leaf_app)]
        root_app = Flama(routes=root_routes, schema=None, docs=None)

        assert len(root_app.router.routes) == 2
        # Check mount is initialized
        assert isinstance(root_app.routes[1], Mount)
        mount_route = root_app.router.routes[1]
        assert mount_route.path == "/app"
        # Check router is created and initialized
        assert isinstance(mount_route.app, Flama)
        mount_app = mount_route.app
        assert isinstance(mount_app.app, Router)
        mount_router = mount_app.app
        # Check main_app is propagated
        assert mount_router.main_app == root_app
        # Check components are collected across the entire tree
        assert mount_router.components == [component_mock]
        assert root_app.components == [component_mock]
        # Check modules are isolated for each app
        assert mount_app.modules == [*DEFAULT_MODULES, module_mock]
        assert root_app.modules == DEFAULT_MODULES

    @pytest.mark.parametrize(
        ["key", "handler"],
        (pytest.param(400, MagicMock(), id="status_code"), pytest.param(ValueError, MagicMock(), id="exception_class")),
    )
    def test_add_exception_handler(self, app, key, handler):
        expected_call = [call(key, handler)]

        with patch.object(app, "middlewares", spec=MiddlewareStack):
            app.add_exception_handler(key, handler)
            assert app.middlewares.add_exception_handler.call_args_list == expected_call

    def test_add_middleware(self, app):
        class FooMiddleware:
            def __call__(self, *args, **kwargs):
                ...

        options = {"foo": "bar"}

        with patch.object(app, "middlewares", spec=MiddlewareStack):
            app.add_middleware(FooMiddleware, **options)
            assert len(app.middlewares.add_middleware.call_args_list) == 1
            middleware = app.middlewares.add_middleware.call_args[0][0]
            assert isinstance(middleware, Middleware)
            assert middleware.cls == FooMiddleware
            assert middleware.options == options

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    async def test_call(self, app, asgi_scope, asgi_receive, asgi_send):
        with patch.object(app, "middlewares", new=AsyncMock(spec=MiddlewareStack)):
            await app(asgi_scope, asgi_receive, asgi_send)
            assert "app" in asgi_scope
            assert asgi_scope["app"] == app
            assert app.middlewares.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]
