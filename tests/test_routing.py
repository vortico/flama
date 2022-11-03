from unittest.mock import MagicMock

import pytest

from flama import endpoints, exceptions
from flama.applications import Flama
from flama.injection import Component, Components
from flama.routing import Mount, Route, Router, WebSocketRoute


class TestCaseRouter:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None)

    @pytest.fixture(scope="function")
    def router(self):
        return Router()

    @pytest.fixture(scope="function")
    def app_mock(self):
        return MagicMock(spec=Flama)

    @pytest.fixture(scope="function")
    def component_mock(self):
        return MagicMock(spec=Component)

    @pytest.fixture(scope="function")
    def scope(self, app):
        return {
            "app": app,
            "client": ["testclient", 50000],
            "endpoint": None,
            "extensions": {"http.response.template": {}},
            "headers": [
                (b"host", b"testserver"),
                (b"user-agent", b"testclient"),
                (b"accept-encoding", b"gzip, deflate"),
                (b"accept", b"*/*"),
                (b"connection", b"keep-alive"),
            ],
            "http_version": "1.1",
            "method": "GET",
            "path": "/",
            "path_params": {},
            "query_string": b"",
            "root_path": "",
            "router": app.router,
            "scheme": "http",
            "server": ["testserver", 80],
            "type": "http",
        }

    def test_add_route(self, router):
        async def foo():
            return "foo"

        router.add_route("/", foo)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo

    def test_add_route_decorator(self, router):
        @router.route("/")
        async def foo():
            return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo

    def test_add_route_endpoint(self, router):
        @router.route("/")
        class FooEndpoint(endpoints.HTTPEndpoint):
            async def get(self):
                return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint

    def test_add_route_wrong_params(self, router):
        with pytest.raises(ValueError, match="Either 'path' and 'endpoint' or 'route' variables are needed"):
            router.add_route()

    def test_add_route_wrong_endpoint(self, router):
        class Foo:
            ...

        endpoint = Foo()

        with pytest.raises(AssertionError, match="Endpoint must be a callable or an HTTPEndpoint subclass"):
            router.add_route(path="/", endpoint=endpoint)

    def test_add_websocket_route(self, router):
        async def foo():
            return "foo"

        router.add_websocket_route("/", foo)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo

    def test_add_websocket_route_decorator(self, router):
        @router.websocket_route("/")
        async def foo():
            return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo

    def test_add_websocket_route_endpoint(self, router):
        @router.websocket_route("/")
        class FooEndpoint(endpoints.WebSocketEndpoint):
            async def on_receive(self, websocket):
                return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint

    def test_add_websocket_route_wrong_params(self, router):
        with pytest.raises(ValueError, match="Either 'path' and 'endpoint' or 'route' variables are needed"):
            router.add_websocket_route()

    def test_add_websocket_route_wrong_endpoint(self, router):
        class Foo:
            ...

        endpoint = Foo()

        with pytest.raises(AssertionError, match="Endpoint must be a callable or a WebSocketEndpoint subclass"):
            router.add_websocket_route(path="/", endpoint=endpoint)

    def test_mount_app(self, app, app_mock):
        app.mount("/app/", app=app_mock)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], Mount)
        assert app.routes[0].path == "/app"
        assert app.routes[0].app == app_mock

    def test_mount_router(self, app, component_mock):
        router = Router(components=[component_mock])

        app.mount("/app/", app=router)

        assert len(app.router.routes) == 1
        # Check mount is initialized
        assert isinstance(app.routes[0], Mount)
        mount_route = app.router.routes[0]
        assert mount_route.path == "/app"
        assert mount_route.main_app == app
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_route.app, Router)
        mount_router = mount_route.app
        assert mount_router.main_app == app
        assert mount_router.components == Components([component_mock])
        assert app.components == Components([component_mock])

    def test_mount_declarative(self, component_mock):
        def root():
            ...

        def foo():
            ...

        def foo_view():
            ...

        routes = [
            Route("/", root),
            Mount(
                "/foo",
                routes=[Route("/", foo, methods=["GET"]), Route("/view", foo_view, methods=["GET"])],
                components={component_mock},
            ),
            Mount(
                "/bar",
                app=Router(
                    routes=[Route("/", foo, methods=["GET"]), Route("/view", foo_view, methods=["GET"])],
                    components={component_mock},
                ),
            ),
        ]

        # Check app is not propagated yet
        assert routes[0].main_app is None

        app = Flama(routes=routes, schema=None, docs=None)

        assert len(app.router.routes) == 3

        # Check first-level route is initialized
        assert isinstance(app.router.routes[0], Route)
        root_route = app.router.routes[0]
        assert root_route.path == "/"
        assert root_route.main_app == app

        # Check mount with routes is initialized
        assert isinstance(app.router.routes[1], Mount)
        mount_with_routes_route = app.router.routes[1]
        assert mount_with_routes_route.main_app == app
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_with_routes_route.app, Router)
        mount_with_routes_router = mount_with_routes_route.app
        assert mount_with_routes_router.main_app == app
        assert mount_with_routes_router.components == Components([component_mock])
        # As the component is repeated, it should appear twice
        assert app.components == Components([component_mock, component_mock])
        # Check second-level routes are created an initialized
        assert len(mount_with_routes_route.routes) == 2
        assert mount_with_routes_route.routes[0].path == "/"
        assert mount_with_routes_route.routes[0].main_app == app
        assert mount_with_routes_route.routes[1].path == "/view"
        assert mount_with_routes_route.routes[1].main_app == app

        # Check mount with app is initialized
        assert isinstance(app.router.routes[2], Mount)
        mount_with_app_route = app.router.routes[2]
        assert mount_with_app_route.main_app == app
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_with_app_route.app, Router)
        mount_with_app_router = mount_with_app_route.app
        assert mount_with_app_router.main_app == app
        assert mount_with_app_router.components == Components([component_mock])
        # As the component is repeated, it should appear twice
        assert app.components == Components([component_mock, component_mock])
        # Check second-level routes are created an initialized
        assert len(mount_with_app_route.routes) == 2
        assert mount_with_app_route.routes[0].path == "/"
        assert mount_with_app_route.routes[0].main_app == app
        assert mount_with_app_route.routes[1].path == "/view"
        assert mount_with_app_route.routes[1].main_app == app

        # Check can delete app
        del app.routes[0].main_app
        del app.routes[1].main_app

        # Check app is deleted in first-level route
        with pytest.raises(AttributeError):
            app.routes[0].main_app

        # Check app is deleted in mount
        with pytest.raises(AttributeError):
            app.routes[1].main_app

        # Check app is deleted in second-level route
        with pytest.raises(AttributeError):
            app.routes[1].routes[0].main_app

    def test_get_route_from_scope_route(self, app, scope):
        @app.route("/foo/")
        async def foo():
            return "foo"

        scope["path"] = "/foo/"
        scope["method"] = "GET"

        route, route_scope = app.router.resolve_route(scope=scope)

        assert route.endpoint == foo
        assert route.path == "/foo/"
        assert route_scope is not None
        assert route_scope["path"] == "/foo/"
        assert route_scope["root_path"] == ""
        assert route_scope["endpoint"] == foo

    def test_get_route_from_scope_mount_view(self, app, router, scope):
        @router.route("/foo/")
        async def foo():
            return "foo"

        app.mount("/router", app=router)

        scope["path"] = "/router/foo/"
        scope["method"] = "GET"

        route, route_scope = app.router.resolve_route(scope=scope)

        assert route.endpoint == foo
        assert route.path == "/foo/"
        assert route_scope is not None
        assert route_scope["path"] == "/foo/"
        assert route_scope["root_path"] == "/router"
        assert route_scope["endpoint"] == foo

    def test_get_route_from_scope_nested_mount_view(self, app, router, scope):
        @router.route("/foo/")
        async def foo():
            return "foo"

        app.mount("/router", app=Router(routes=[Mount("/nested", app=router)]))

        scope["path"] = "/router/nested/foo/"
        scope["method"] = "GET"

        route, route_scope = app.router.resolve_route(scope=scope)

        assert route_scope is not None
        assert route.endpoint == foo
        assert route.path == "/foo/"
        assert route_scope["path"] == "/foo/"
        assert route_scope["root_path"] == "/router/nested"
        assert route_scope["endpoint"] == foo

    def test_get_route_from_scope_partial(self, app, scope):
        @app.route("/foo/")
        async def foo():
            return "foo"

        scope["path"] = "/foo/"
        scope["method"] = "POST"

        with pytest.raises(exceptions.MethodNotAllowedException):
            route, route_scope = app.router.resolve_route(scope=scope)

    def test_get_route_from_scope_not_found(self, app, scope):
        scope["path"] = "/foo/"
        scope["method"] = "GET"

        with pytest.raises(exceptions.NotFoundException):
            route, route_scope = app.router.resolve_route(scope=scope)
