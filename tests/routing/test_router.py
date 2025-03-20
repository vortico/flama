import collections
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import exceptions, types, url
from flama.applications import Flama
from flama.client import Client
from flama.endpoints import HTTPEndpoint, WebSocketEndpoint
from flama.injection import Component, Components
from flama.lifespan import Lifespan
from flama.routing.router import Router
from flama.routing.routes.http import Route
from flama.routing.routes.mount import Mount
from flama.routing.routes.websocket import WebSocketRoute


class TestCaseRouter:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None)

    @pytest.fixture(scope="function")
    def router(self, app):
        return Router(root=app)

    @pytest.fixture(scope="function")
    def app_mock(self):
        return MagicMock(spec=Flama, router=MagicMock(spec=Router, components=Components([])))

    @pytest.fixture(scope="function")
    def component_mock(self):
        return MagicMock(spec=Component)

    @pytest.fixture(scope="function")
    def tags(self):
        return {"tag": "foo", "list_tag": ["foo", "bar"], "dict_tag": {"foo": "bar"}}

    @pytest.fixture(scope="function")
    def endpoint(self, request, router):  # noqa: C901
        if request.param == "function":

            async def foo():
                return "foo"

            def mount(app):
                app.add_route("/foo/", foo)

            endpoint = foo
        elif request.param == "endpoint":

            class FooHTTPEndpoint(HTTPEndpoint):
                async def get(self):
                    return "foo"

            def mount(app):
                app.add_route("/foo/", FooHTTPEndpoint)

            endpoint = FooHTTPEndpoint
        elif request.param == "websocket_function":

            async def foo():
                return "foo"

            def mount(app):
                app.add_websocket_route("/foo/", foo)

            endpoint = foo
        elif request.param == "websocket_endpoint":

            class FooWebSocketEndpoint(WebSocketEndpoint): ...

            def mount(app):
                app.add_websocket_route("/foo/", FooWebSocketEndpoint)

            endpoint = FooWebSocketEndpoint
        elif request.param == "nested_app":

            async def foo():
                return "foo"

            nested = Flama()
            nested.add_route("/foo/", foo)

            def mount(app):
                app.mount("/nested", app=nested)

            endpoint = foo
        elif request.param == "nested_router":

            async def foo():
                return "foo"

            router.add_route("/foo/", foo)

            def mount(app):
                app.mount("/router", app=router)

            endpoint = foo
        elif request.param == "nested_app_nested_router":

            async def foo():
                return "foo"

            nested = Flama()
            router.add_route("/foo/", foo)
            nested.mount("/router", app=router)

            def mount(app):
                app.mount("/nested", app=nested)

            endpoint = foo
        elif request.param == "wrong":

            class Foo: ...

            def mount(app):
                app.add_route("/wrong/", Foo)

            endpoint = Foo
        else:
            raise ValueError(f"Wrong value: {request.param}")

        return collections.namedtuple("Endpoint", ("endpoint", "mount"))(endpoint, mount)

    def test_init(self, app_mock):
        with patch("flama.routing.Router.build") as method_mock:
            Router([], root=app_mock)

        assert method_mock.call_args_list == [call(app_mock)]

    def test_eq(self):
        route = MagicMock(Route)
        assert Router(routes=[route]) == Router(routes=[route])

    @pytest.mark.parametrize(
        ["request_type"],
        (
            pytest.param("http", id="http"),
            pytest.param("websocket", id="websocket"),
        ),
    )
    async def test_call_route(self, request_type, router, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = request_type

        route = AsyncMock()
        route_scope = types.Scope({})
        with patch.object(router, "resolve_route", return_value=(route, route_scope)):
            await router(asgi_scope, asgi_receive, asgi_send)

        assert route.call_args_list == [call(route_scope, asgi_receive, asgi_send)]

    async def test_call_lifespan(self, router, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "lifespan"

        lifespan_mock = AsyncMock(Lifespan)
        with patch.object(router, "lifespan", lifespan_mock):
            await router(asgi_scope, asgi_receive, asgi_send)

        assert lifespan_mock.await_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    def test_build(self, router):
        app = MagicMock(Flama)
        route = MagicMock(Route)

        # First call to build when adding route
        router.add_route(route=route, root=app)

        # Second call to build
        router.build(app)

        assert route.build.call_args_list == [call(app), call(app)]

    def test_components(self, router, component_mock):
        assert router.components == []

        router.add_component(component_mock)
        leaf_component = MagicMock(spec=Component)
        leaf_router = Router(components=[leaf_component])
        router.mount("/app/", app=leaf_router)

        assert router.components == [component_mock]
        # Components are not propagated to leaf because mounted was done through a router instead of app
        assert leaf_router.components == [leaf_component]

    def test_add_component(self, router, component_mock):
        assert router.components == []

        router.add_component(component_mock)

        assert router.components == [component_mock]

    @pytest.mark.parametrize(
        ["endpoint", "path", "exception"],
        [
            pytest.param(
                "function",
                "/",
                None,
                id="function",
            ),
            pytest.param(
                "endpoint",
                "/",
                None,
                id="endpoint",
            ),
            pytest.param(
                "function",
                None,
                exceptions.ApplicationError("Either 'path' and 'endpoint' or 'route' variables are needed"),
                id="no_path",
            ),
            pytest.param(
                "wrong",
                "/",
                exceptions.ApplicationError("Endpoint must be a callable or an HTTPEndpoint subclass"),
                id="wrong_endpoint",
            ),
        ],
        indirect=["endpoint", "exception"],
    )
    def test_add_route(self, router, tags, endpoint, path, exception):
        with exception:
            router.add_route(path, endpoint.endpoint, tags=tags)

            assert len(router.routes) == 1
            assert isinstance(router.routes[0], Route)
            assert router.routes[0].path == path
            assert router.routes[0].endpoint == endpoint.endpoint
            assert router.routes[0].tags == tags

    @pytest.mark.parametrize(
        ["endpoint", "path", "exception"],
        [
            pytest.param(
                "function",
                "/",
                None,
                id="function",
            ),
            pytest.param(
                "endpoint",
                "/",
                None,
                id="endpoint",
            ),
            pytest.param(
                "function",
                None,
                exceptions.ApplicationError("Either 'path' and 'endpoint' or 'route' variables are needed"),
                id="no_path",
            ),
            pytest.param(
                "wrong",
                "/",
                exceptions.ApplicationError("Endpoint must be a callable or an HTTPEndpoint subclass"),
                id="wrong_endpoint",
            ),
        ],
        indirect=["endpoint", "exception"],
    )
    def test_route(self, router, tags, endpoint, path, exception):
        with exception:
            router.route(path, tags=tags)(endpoint.endpoint)

            assert len(router.routes) == 1
            assert isinstance(router.routes[0], Route)
            assert router.routes[0].path == path
            assert router.routes[0].endpoint == endpoint.endpoint
            assert router.routes[0].tags == tags

    @pytest.mark.parametrize(
        ["endpoint", "path", "exception"],
        [
            pytest.param(
                "websocket_function",
                "/",
                None,
                id="function",
            ),
            pytest.param(
                "websocket_endpoint",
                "/",
                None,
                id="endpoint",
            ),
            pytest.param(
                "function",
                None,
                exceptions.ApplicationError("Either 'path' and 'endpoint' or 'route' variables are needed"),
                id="no_path",
            ),
            pytest.param(
                "wrong",
                "/",
                exceptions.ApplicationError("Endpoint must be a callable or a WebSocketEndpoint subclass"),
                id="wrong_endpoint",
            ),
        ],
        indirect=["endpoint", "exception"],
    )
    def test_add_websocket(self, router, tags, endpoint, path, exception):
        with exception:
            router.add_websocket_route(path, endpoint.endpoint, tags=tags)

            assert len(router.routes) == 1
            assert isinstance(router.routes[0], WebSocketRoute)
            assert router.routes[0].path == path
            assert router.routes[0].endpoint == endpoint.endpoint
            assert router.routes[0].tags == tags

    @pytest.mark.parametrize(
        ["endpoint", "path", "exception"],
        [
            pytest.param(
                "websocket_function",
                "/",
                None,
                id="function",
            ),
            pytest.param(
                "websocket_endpoint",
                "/",
                None,
                id="endpoint",
            ),
            pytest.param(
                "function",
                None,
                exceptions.ApplicationError("Either 'path' and 'endpoint' or 'route' variables are needed"),
                id="no_path",
            ),
            pytest.param(
                "wrong",
                "/",
                exceptions.ApplicationError("Endpoint must be a callable or a WebSocketEndpoint subclass"),
                id="wrong_endpoint",
            ),
        ],
        indirect=["endpoint", "exception"],
    )
    def test_websocket_route_function(self, router, tags, endpoint, path, exception):
        with exception:
            router.websocket_route(path, tags=tags)(endpoint.endpoint)

            assert len(router.routes) == 1
            assert isinstance(router.routes[0], WebSocketRoute)
            assert router.routes[0].path == path
            assert router.routes[0].endpoint == endpoint.endpoint
            assert router.routes[0].tags == tags

    def test_mount_app(self, app, app_mock, tags):
        app.mount("/app/", app=app_mock, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], Mount)
        assert app.routes[0].path == "/app/"
        assert app.routes[0].app == app_mock
        assert app.routes[0].tags == tags

    def test_mount_router(self, app, component_mock, tags):
        router = Router(components=[component_mock])

        app.mount("/app/", app=router, tags=tags)

        assert len(app.router.routes) == 1
        # Check mount is initialized
        assert isinstance(app.routes[0], Mount)
        mount_route = app.router.routes[0]
        assert mount_route.path == "/app/"
        assert mount_route.tags == tags
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_route.app, Router)
        mount_router = mount_route.app
        default_components = app.components[:1]
        assert mount_router.components == [component_mock]
        assert app.components == default_components

    def test_mount_declarative(self, component_mock, tags):
        def root(): ...

        def foo(): ...

        def foo_view(): ...

        routes = [
            Route("/", root, tags=tags),
            Mount(
                "/foo",
                routes=[Route("/", foo, methods=["GET"]), Route("/view", foo_view, methods=["GET"])],
                components=[component_mock],
                tags=tags,
            ),
            Mount(
                "/bar",
                app=Router(
                    routes=[Route("/", foo, methods=["GET"]), Route("/view", foo_view, methods=["GET"])],
                    components=[component_mock],
                ),
                tags=tags,
            ),
        ]

        app = Flama(routes=routes, schema=None, docs=None)

        assert len(app.router.routes) == 3

        # Check first-level route is initialized
        assert isinstance(app.router.routes[0], Route)
        root_route = app.router.routes[0]
        assert root_route.path == "/"
        assert root_route.tags == tags

        # Check mount with routes is initialized
        assert isinstance(app.router.routes[1], Mount)
        mount_with_routes_route = app.router.routes[1]
        assert mount_with_routes_route.path == "/foo"
        assert mount_with_routes_route.tags == tags
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_with_routes_route.app, Router)
        mount_with_routes_router = mount_with_routes_route.app
        assert mount_with_routes_router.components == [component_mock]
        default_components = app.components[:1]
        assert app.components == default_components
        # Check second-level routes are created an initialized
        assert len(mount_with_routes_route.routes) == 2
        assert mount_with_routes_route.routes[0].path == "/"
        assert mount_with_routes_route.routes[1].path == "/view"

        # Check mount with app is initialized
        assert isinstance(app.router.routes[2], Mount)
        mount_with_app_route = app.router.routes[2]
        assert mount_with_app_route.path == "/bar"
        assert mount_with_app_route.tags == tags
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_with_app_route.app, Router)
        mount_with_app_router = mount_with_app_route.app
        assert mount_with_app_router.components == [component_mock]
        assert app.components == default_components
        # Check second-level routes are created an initialized
        assert len(mount_with_app_route.routes) == 2
        assert mount_with_app_route.routes[0].path == "/"
        assert mount_with_app_route.routes[1].path == "/view"

    @pytest.mark.parametrize(
        ["endpoint", "path", "root_path", "endpoint_path", "method", "exception"],
        [
            pytest.param("function", "/foo/", "", "/foo/", "GET", None, id="function"),
            pytest.param("endpoint", "/foo/", "", "/foo/", "GET", None, id="endpoint"),
            pytest.param("nested_app", "/nested/foo/", "", "/foo/", "GET", None, id="nested_app"),
            pytest.param("nested_router", "/router/foo/", "/router", "/foo/", "GET", None, id="nested_router"),
            pytest.param(
                "nested_app_nested_router",
                "/nested/router/foo/",
                "/router",
                "/foo/",
                "GET",
                None,
                id="nested_app_nested_router",
            ),
            pytest.param("function", "/foo/", "", "/foo/", "POST", exceptions.MethodNotAllowedException, id="partial"),
            pytest.param("function", "/bar/", "", "/foo/", "GET", exceptions.NotFoundException, id="not_found"),
        ],
        indirect=["endpoint", "exception"],
    )
    def test_resolve_route(self, app, endpoint, path, root_path, endpoint_path, method, asgi_scope, exception):
        endpoint.mount(app)

        asgi_scope["path"] = path
        asgi_scope["method"] = method

        with exception:
            route, route_scope = app.router.resolve_route(scope=asgi_scope)

            assert route.endpoint == endpoint.endpoint
            assert route.path == "/foo/"
            assert route_scope["root_path"] == root_path
            assert route_scope["path"] == endpoint_path

    @pytest.mark.parametrize(
        ["routes", "result", "exception"],
        (
            pytest.param(
                [
                    MagicMock(spec=Route, resolve_url=MagicMock(return_value=url.URL("/foo"))),
                    MagicMock(spec=Route, resolve_url=MagicMock(side_effect=exceptions.NotFoundException)),
                ],
                url.URL("/foo"),
                None,
                id="first",
            ),
            pytest.param(
                [
                    MagicMock(spec=Route, resolve_url=MagicMock(side_effect=exceptions.NotFoundException)),
                    MagicMock(spec=Route, resolve_url=MagicMock(return_value=url.URL("/foo"))),
                ],
                url.URL("/foo"),
                None,
                id="other",
            ),
            pytest.param(
                [
                    MagicMock(spec=Route, resolve_url=MagicMock(side_effect=exceptions.NotFoundException)),
                    MagicMock(spec=Route, resolve_url=MagicMock(side_effect=exceptions.NotFoundException)),
                ],
                None,
                exceptions.NotFoundException,
                id="not_found",
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve_url(self, router, routes, result, exception):
        for route in routes:
            router.add_route(route=route)

        with exception:
            assert router.resolve_url("foo") == result

    async def test_request_nested_app(self, app):
        sub_app = Flama(docs=None, schema=None)
        sub_app.add_route("/bar/", lambda: {"foo": "bar"}, ["GET"])

        app.mount("/foo", sub_app)

        async with Client(app) as client:
            response = await client.get("/foo/bar/")
            assert response.status_code == 200
            assert response.json() == {"foo": "bar"}
