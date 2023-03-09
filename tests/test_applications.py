import sys
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from flama import Component, Flama, Module, Mount, Route, Router, exceptions, http, types, websockets
from flama.events import Events
from flama.injection.injector import Injector
from flama.middleware import Middleware, MiddlewareStack
from flama.models import ModelsModule
from flama.resources import BaseResource, ResourcesModule, ResourceType, resource_method
from flama.routing import BaseRoute
from flama.schemas.modules import SchemaModule
from flama.url import URL

if sys.version_info >= (3, 8):  # PORT: Remove when stop supporting 3.7 # pragma: no cover
    from unittest.mock import AsyncMock
else:  # pragma: no cover
    from asyncmock import AsyncMock

DEFAULT_MODULES = [ResourcesModule, SchemaModule, ModelsModule]


class TestCaseFlama:
    @pytest.fixture(scope="function")
    def component(self):
        return MagicMock(spec=Component)

    @pytest.fixture(scope="function")
    def module(self):
        class Foo(Module):
            name = "foo"

        return Foo

    @pytest.fixture(scope="function")
    def middleware(self):
        return MagicMock(spec=Middleware)

    @pytest.fixture
    def app(self):
        return Flama(schema=None, docs=None)

    @pytest.fixture(scope="function")
    def tags(self):
        return {"tag": "foo", "list_tag": ["foo", "bar"], "dict_tag": {"foo": "bar"}}

    def test_init(self, module, component):
        component_obj = component()

        app = Flama(components=[component_obj], modules={module()})

        # Check router and main app
        assert isinstance(app.app, Router)
        assert isinstance(app.router, Router)
        # Check injector
        assert isinstance(app._injector, Injector)
        assert app._injector.context_types == {
            "scope": types.Scope,
            "receive": types.Receive,
            "send": types.Send,
            "exc": Exception,
            "app": Flama,
            "path_params": types.PathParams,
            "route": BaseRoute,
            "request": http.Request,
            "response": http.Response,
            "websocket": websockets.WebSocket,
            "websocket_message": types.Message,
            "websocket_encoding": types.Encoding,
            "websocket_code": types.Code,
        }
        assert app._injector.components == []
        # Check middleware
        assert isinstance(app.middleware, MiddlewareStack)
        assert app.middleware
        # Check modules
        assert app.modules == {ResourcesModule, SchemaModule, ModelsModule, module}
        # Check components
        assert app.components == [component_obj]
        # Check events
        assert app.events == Events(
            startup=[m.on_startup for m in app.modules.values()], shutdown=[m.on_shutdown for m in app.modules.values()]
        )

    def test_getattr(self, app):
        for name, module in app.modules.items():
            assert getattr(app, name) == module

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    async def test_call(self, app, asgi_scope, asgi_receive, asgi_send):
        with patch.object(app, "middleware", new=AsyncMock(spec=MiddlewareStack)):
            await app(asgi_scope, asgi_receive, asgi_send)
            assert "app" in asgi_scope
            assert asgi_scope["app"] == app
            assert app.middleware.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    def test_components(self, app):
        expected_components = [MagicMock()]
        components_mock = PropertyMock(return_value=expected_components)

        with patch.object(Router, "components", new=components_mock):
            components = app.components

        assert components_mock.call_args_list == [call()]
        assert components == expected_components

    def test_add_component(self, app, component):
        component_obj = component()

        with patch.object(app, "router", spec=Router) as router_mock:
            app.add_component(component_obj)

        assert router_mock.add_component.call_args_list == [call(component_obj)]
        assert router_mock.build.call_args_list == [call(app)]

    def test_routes(self, app):
        expected_routes = [MagicMock()]
        with patch.object(app, "router", spec=Router) as router_mock:
            router_mock.routes = expected_routes
            routes = app.routes

        assert routes == expected_routes

    def test_add_route(self, app, tags):
        def foo():
            ...

        with patch.object(app, "router", spec=Router) as router_mock:
            router_mock.add_route.return_value = foo
            route = app.add_route("/", foo, **tags)

        assert router_mock.add_route.call_args_list == [
            call("/", foo, methods=None, name=None, include_in_schema=True, route=None, root=app, **tags)
        ]
        assert route == foo

    def test_route(self, app, tags):
        with patch.object(app, "router", spec=Router) as router_mock:

            @app.route("/", **tags)
            def foo():
                ...

        assert router_mock.route.call_args_list == [
            call("/", methods=None, name=None, include_in_schema=True, root=app, **tags)
        ]

    def test_add_websocket_route(self, app, tags):
        def foo():
            ...

        with patch.object(app, "router", spec=Router) as router_mock:
            router_mock.add_websocket_route.return_value = foo
            route = app.add_websocket_route("/", foo, **tags)

        assert router_mock.add_websocket_route.call_args_list == [
            call("/", foo, name=None, route=None, root=app, **tags)
        ]
        assert route == foo

    def test_websocket_route(self, app, tags):
        with patch.object(app, "router", spec=Router) as router_mock:

            @app.websocket_route("/", **tags)
            def foo():
                ...

        assert router_mock.websocket_route.call_args_list == [call("/", name=None, root=app, **tags)]

    def test_mount(self, app, tags):
        expected_mount = MagicMock()

        with patch.object(app, "router", spec=Router) as router_mock:
            router_mock.mount.return_value = expected_mount
            mount = app.mount("/", expected_mount, **tags)

        assert router_mock.mount.call_args_list == [call("/", expected_mount, name=None, mount=None, root=app, **tags)]
        assert mount == expected_mount

    def test_injector(self, app):
        assert isinstance(app.injector, Injector)

    def test_add_event_handler(self, app):
        handlers_before = app.events.startup.copy()

        def handler():
            ...

        app.add_event_handler("startup", handler)

        assert app.events.startup == [*handlers_before, handler]

    def test_on_event(self, app):
        handlers_before = app.events.startup.copy()

        @app.on_event("startup")
        def handler():
            ...

        assert app.events.startup == [*handlers_before, handler]

    @pytest.mark.parametrize(
        ["key", "handler"],
        (pytest.param(400, MagicMock(), id="status_code"), pytest.param(ValueError, MagicMock(), id="exception_class")),
    )
    def test_add_exception_handler(self, app, key, handler):
        expected_call = [call(key, handler)]

        with patch.object(app, "middleware", spec=MiddlewareStack):
            app.add_exception_handler(key, handler)
            assert app.middleware.add_exception_handler.call_args_list == expected_call

    def test_add_middleware(self, app):
        class FooMiddleware:
            def __call__(self, app: types.App, *args, **kwargs):
                ...

        kwargs = {"foo": "bar"}

        with patch.object(app, "middleware", spec=MiddlewareStack):
            app.add_middleware(Middleware(FooMiddleware, **kwargs))
            assert len(app.middleware.add_middleware.call_args_list) == 1
            middleware = app.middleware.add_middleware.call_args[0][0]
            assert isinstance(middleware, Middleware)
            assert middleware.middleware == FooMiddleware
            assert middleware.kwargs == kwargs

    @pytest.mark.parametrize(
        ["resolve", "path_params", "resolution", "exception"],
        (
            pytest.param("foo", {}, URL(scheme="http", path="/foo"), None, id="plain"),
            pytest.param("foo", {"x": 1}, URL(scheme="http", path="/foo/1"), None, id="path_params"),
            pytest.param("foo:bar", {}, URL(scheme="http", path="/foo/bar"), None, id="nested"),
            pytest.param(
                "puppy:custom", {}, URL(scheme="http", path="/puppy/custom"), None, id="resource_custom_method"
            ),
            pytest.param(
                "not-found", {}, None, exceptions.NotFoundException(params={}, name="not-found"), id="not_found"
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve_url(self, app, resolve, path_params, resolution, exception):
        app.add_route(route=Route("/foo", lambda: None, name="foo"))
        app.add_route(route=Route("/foo/{x:int}", lambda: None, name="foo"))
        app.mount(mount=Mount("/foo", routes=[Route("/bar", lambda: None, name="bar")], name="foo"))

        @app.resources.resource("/puppy")
        class PuppyResource(BaseResource, metaclass=ResourceType):
            name = "puppy"
            verbose_name = "Puppy"

            @resource_method("/custom")
            def custom(self):
                ...

        with exception:
            assert app.resolve_url(resolve, **path_params) == resolution

    def test_end_to_end(self, component, module):
        """Test"""
        root_app = Flama(schema=None, docs=None)
        root_app.add_get("/foo", lambda: {})

        assert len(root_app.router.routes) == 1
        assert root_app.components == set()
        assert root_app.modules == DEFAULT_MODULES

        leaf_app = Flama(schema=None, docs=None, components=[component], modules={module()})
        leaf_app.add_get("/bar", lambda: {})

        assert len(leaf_app.router.routes) == 1
        assert leaf_app.components == [component]
        assert leaf_app.modules == [*DEFAULT_MODULES, module]

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
        # Check components are collected across the entire tree
        assert mount_router.components == [component]
        assert root_app.components == [component]
        # Check modules are isolated for each app
        assert mount_app.modules == [*DEFAULT_MODULES, module]
        assert root_app.modules == DEFAULT_MODULES

    def test_end_to_end_declarative(self, component, module):
        leaf_routes = [Route("/bar", lambda: {})]
        leaf_app = Flama(routes=leaf_routes, schema=None, docs=None, components=[component], modules={module()})
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
        # Check components are collected across the entire tree
        assert mount_router.components == [component]
        assert root_app.components == [component]
        # Check modules are isolated for each app
        assert mount_app.modules == [*DEFAULT_MODULES, module]
        assert root_app.modules == DEFAULT_MODULES
