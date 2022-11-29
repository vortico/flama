import sys
from unittest.mock import MagicMock, call, patch

import pytest

from flama import endpoints, exceptions, types, url, websockets
from flama.applications import Flama
from flama.endpoints import HTTPEndpoint, WebSocketEndpoint
from flama.injection import Component, Components
from flama.routing import BaseRoute, EndpointWrapper, Match, Mount, Route, Router, WebSocketRoute

if sys.version_info >= (3, 8):  # PORT: Remove when stop supporting 3.7 # pragma: no cover
    from unittest.mock import AsyncMock
else:  # pragma: no cover
    from asyncmock import AsyncMock


class TestCaseBaseRoute:
    @pytest.fixture(scope="function")
    def route(self):
        return BaseRoute(
            "/", EndpointWrapper(lambda: None, EndpointWrapper.type.http), name="foo", include_in_schema=False
        )

    def test_init(self):
        def foo():
            ...

        app = EndpointWrapper(foo, EndpointWrapper.type.http)
        route = BaseRoute("/", app, name="foo", include_in_schema=False)

        assert route.path == url.RegexPath("/")
        assert route.app == app
        assert route.endpoint == foo
        assert route.name == "foo"
        assert route.include_in_schema is False

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    async def test_call(self, route, asgi_scope, asgi_receive, asgi_send):
        route_scope = types.Scope({"foo": "bar"})
        handle = AsyncMock()

        with patch.object(route, "handle", new=handle), patch.object(route, "route_scope", return_value=route_scope):
            await route(asgi_scope, asgi_receive, asgi_send)

        assert handle.call_args_list == [call(types.Scope({**asgi_scope, **route_scope}), asgi_receive, asgi_send)]

    def test_eq(self):
        def foo():
            ...

        assert BaseRoute("/", foo, name="foo") == BaseRoute("/", foo, name="foo")
        assert BaseRoute("/", foo, name="foo") != BaseRoute("/", foo, name="bar")

    def test_repr(self):
        def foo():
            ...

        assert repr(BaseRoute("/", foo, name="foo")) == "BaseRoute(path='/', name='foo')"

    @pytest.mark.parametrize(["app"], (pytest.param(MagicMock(spec=Flama), id="app"), pytest.param(None, id="no_app")))
    def test_build(self, app, route):
        expected_calls = [call(app)] if app else []
        with patch.object(route, "parameters") as parameters_mock:
            route.build(app)

        assert parameters_mock.build.call_args_list == expected_calls

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    async def test_handle(self, asgi_scope, asgi_receive, asgi_send):
        app = AsyncMock()
        route = BaseRoute("/", app)

        await route.handle(asgi_scope, asgi_receive, asgi_send)

        assert app.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    @pytest.mark.parametrize(
        ["path_match_return", "result"],
        (
            pytest.param(True, Match.full, id="match"),
            pytest.param(False, Match.none, id="no_match"),
        ),
    )
    def test_match(self, path_match_return, result, route, asgi_scope):
        with patch.object(route.path, "match", return_value=path_match_return):
            assert route.match(asgi_scope) == result

    def test_route_scope(self, asgi_scope):
        app = AsyncMock()
        route = BaseRoute("/", app)
        path_values = {"foo": "bar"}

        with patch.object(route.path, "values", return_value=path_values):
            route_scope = route.route_scope(asgi_scope)

        assert route_scope == types.Scope({"endpoint": app, "path_params": path_values})

    @pytest.mark.parametrize(
        ["name", "params", "exception"],
        (
            pytest.param("foo", {"bar": 1}, None, id="found"),
            pytest.param("bar", {}, exceptions.NotFoundException(name="bar", params={}), id="not_found_wrong_name"),
            pytest.param(
                "foo",
                {"wrong": 1},
                exceptions.NotFoundException(name="foo", params={"wrong": 1}),
                id="not_found_wrong_params",
            ),
            pytest.param(
                "foo",
                {"bar": 1, "wrong": 1},
                exceptions.NotFoundException(name="foo", params={"bar": 1, "wrong": 1}),
                id="error_remaining_params",
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve_url(self, name, params, exception):
        route = BaseRoute("/foo/{bar:int}", lambda bar: None, name="foo")

        with exception:
            assert route.resolve_url(name=name, **params)


class TestCaseRoute:
    @pytest.fixture(scope="function")
    def endpoint(self, request):
        if request.param == "function":

            def foo():
                ...

            return foo

        elif request.param == "endpoint":

            class FooEndpoint(HTTPEndpoint):
                def get(self):
                    ...

                def post(self):
                    ...

            return FooEndpoint

    @pytest.mark.parametrize(
        ["endpoint", "name", "methods", "expected_methods"],
        (
            pytest.param("function", "foo", {"GET", "POST"}, {"GET", "POST", "HEAD"}, id="function_explicit_methods"),
            pytest.param(
                "endpoint", "FooEndpoint", {"GET", "POST"}, {"GET", "POST", "HEAD"}, id="endpoint_explicit_methods"
            ),
            pytest.param("function", "foo", None, {"GET", "HEAD"}, id="function_no_methods"),
            pytest.param("endpoint", "FooEndpoint", None, {"GET", "POST", "HEAD"}, id="endpoint_no_methods"),
        ),
        indirect=["endpoint"],
    )
    def test_init(self, endpoint, name, methods, expected_methods):
        route = Route("/", endpoint, methods=methods, include_in_schema=False)

        assert route.path == url.RegexPath("/")
        assert isinstance(route.app, EndpointWrapper)
        assert route.endpoint == endpoint
        assert route.name == name
        assert route.include_in_schema is False
        assert route.methods == expected_methods

    def test_eq(self):
        def foo():
            ...

        assert Route("/", foo, methods={"GET"}) == Route("/", foo, methods={"GET"})
        assert Route("/", foo, methods={"GET"}) != Route("/", foo, methods={"POST"})

    def test_repr(self):
        def foo():
            ...

        assert repr(Route("/", foo)) == "Route(path='/', name='foo', methods=['GET', 'HEAD'])"

    @pytest.mark.parametrize(
        ["endpoint", "result"],
        (
            pytest.param("function", False, id="function"),
            pytest.param("endpoint", True, id="endpoint"),
        ),
        indirect=["endpoint"],
    )
    def test_is_endpoint(self, endpoint, result):
        assert Route.is_endpoint(endpoint) is result

    @pytest.mark.parametrize(
        ["endpoint", "methods", "expected_methods"],
        (
            pytest.param("function", {"GET"}, {"GET", "HEAD"}, id="function_explicit_methods"),
            pytest.param("endpoint", {"GET"}, {"GET", "HEAD"}, id="endpoint_explicit_methods"),
            pytest.param("function", None, {"GET", "HEAD"}, id="function_no_methods"),
            pytest.param("endpoint", None, {"GET", "HEAD", "POST"}, id="endpoint_no_methods"),
        ),
        indirect=["endpoint"],
    )
    def test_endpoint_handlers(self, endpoint, methods, expected_methods):
        result = {m: getattr(endpoint, m.lower() if m != "HEAD" else "get", endpoint) for m in expected_methods}

        route = Route("/", endpoint, methods=methods)

        assert route.endpoint_handlers() == result

    @pytest.mark.parametrize(
        ["scope_type", "scope_method", "path_match_return", "result"],
        (
            pytest.param("http", "GET", Match.full, Match.full, id="match"),
            pytest.param("http", "POST", Match.full, Match.partial, id="partial"),
            pytest.param("http", "GET", Match.none, Match.none, id="no_match"),
            pytest.param("websocket", "GET", None, Match.none, id="wrong_scope_type"),
        ),
    )
    def test_match(self, scope_type, scope_method, path_match_return, result, asgi_scope):
        def foo():
            ...

        route = Route("/", foo, methods={"GET"})

        asgi_scope["type"] = scope_type
        asgi_scope["method"] = scope_method

        with patch.object(BaseRoute, "match", return_value=path_match_return):
            assert route.match(asgi_scope) == result


class TestCaseWebsocketRoute:
    @pytest.fixture(scope="function")
    def endpoint(self, request):
        if request.param == "function":

            def foo():
                ...

            return foo

        elif request.param == "endpoint":

            class FooEndpoint(WebSocketEndpoint):
                def on_receive(self, websocket: websockets.WebSocket, data: types.Data) -> None:
                    ...

            return FooEndpoint

    @pytest.mark.parametrize(
        ["endpoint", "name"],
        (
            pytest.param("function", "foo", id="function"),
            pytest.param("endpoint", "FooEndpoint", id="endpoint"),
        ),
        indirect=["endpoint"],
    )
    def test_init(self, endpoint, name):
        route = WebSocketRoute("/", endpoint, include_in_schema=False)

        assert route.path == url.RegexPath("/")
        assert isinstance(route.app, EndpointWrapper)
        assert route.endpoint == endpoint
        assert route.name == name
        assert route.include_in_schema is False

    def test_eq(self):
        def foo():
            ...

        assert WebSocketRoute("/", foo, name="foo") == WebSocketRoute("/", foo, name="foo")
        assert WebSocketRoute("/", foo, name="foo") != WebSocketRoute("/", foo, name="bar")

    @pytest.mark.parametrize(
        ["endpoint", "result"],
        (
            pytest.param("function", False, id="function"),
            pytest.param("endpoint", True, id="endpoint"),
        ),
        indirect=["endpoint"],
    )
    def test_is_endpoint(self, endpoint, result):
        assert WebSocketRoute.is_endpoint(endpoint) is result

    @pytest.mark.parametrize(
        ["endpoint", "expected_handlers"],
        (
            pytest.param("function", {"WEBSOCKET"}, id="function"),
            pytest.param("endpoint", {"WEBSOCKET_CONNECT", "WEBSOCKET_RECEIVE", "WEBSOCKET_DISCONNECT"}, id="endpoint"),
        ),
        indirect=["endpoint"],
    )
    def test_endpoint_handlers(self, endpoint, expected_handlers):
        result = {x: getattr(endpoint, x.lower().replace("websocket", "on"), endpoint) for x in expected_handlers}

        route = WebSocketRoute("/", endpoint)

        assert route.endpoint_handlers() == result

    @pytest.mark.parametrize(
        ["scope_type", "path_match_return", "result"],
        (
            pytest.param("websocket", Match.full, Match.full, id="match"),
            pytest.param("websocket", Match.none, Match.none, id="no_match"),
            pytest.param("http", None, Match.none, id="wrong_scope_type"),
        ),
    )
    def test_match(self, scope_type, path_match_return, result, asgi_scope):
        def foo():
            ...

        route = WebSocketRoute("/", foo)

        asgi_scope["type"] = scope_type

        with patch.object(BaseRoute, "match", return_value=path_match_return):
            assert route.match(asgi_scope) == result


class TestCaseMount:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None)

    @pytest.fixture(scope="function")
    def mount(self, app):
        return Mount("/foo/{x:int}/", app, name="foo")

    @pytest.mark.parametrize(
        ["app", "routes", "exception"],
        (
            pytest.param(MagicMock(spec=Flama), None, None, id="app"),
            pytest.param(None, [MagicMock(spec=Route)], None, id="routes"),
            pytest.param(None, None, AssertionError, id="wrong"),
        ),
        indirect=["exception"],
    )
    def test_init(self, app, routes, exception):
        with exception:
            mount = Mount("/foo/", app, routes=routes)

            if app is None and routes:
                app = Router(routes=routes)

            assert mount.app == app
            assert mount.path == "/foo"

    def test_eq(self, app):
        assert Mount("/", app, name="app_mock") == Mount("/", app, name="app_mock")
        assert Mount("/", app, name="app_mock") != Mount("/", app, name="bar")

    def test_build(self, mount, app):
        route = MagicMock(spec=Route)
        mount.app = MagicMock(spec=Flama)
        mount.app.routes = [route]

        mount.build(app)

        assert route.build.call_args_list == [call(app)]

    @pytest.mark.parametrize(
        ["scope_type", "path_match_return", "result"],
        (
            pytest.param("http", Match.full, Match.full, id="match-http"),
            pytest.param("http", Match.none, Match.none, id="no_match-http"),
            pytest.param("websocket", Match.full, Match.full, id="match-websocket"),
            pytest.param("websocket", Match.none, Match.none, id="no_match-websocket"),
            pytest.param("wrong", None, Match.none, id="wrong_scope_type"),
        ),
    )
    def test_match(self, scope_type, path_match_return, result, asgi_scope, mount):
        asgi_scope["type"] = scope_type

        with patch.object(BaseRoute, "match", return_value=path_match_return):
            assert mount.match(asgi_scope) == result

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    async def test_handle(self, mount, asgi_scope, asgi_receive, asgi_send):
        mount = Mount("/", AsyncMock(spec=Flama))

        await mount.handle(asgi_scope, asgi_receive, asgi_send)

        assert mount.app.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    def test_route_scope(self, mount, asgi_scope):
        def bar():
            ...

        mount.app.add_route("/bar", bar)

        asgi_scope["path"] = "/foo/1/bar"
        route_scope = mount.route_scope(asgi_scope)

        assert route_scope == {"endpoint": mount.app, "path": "/bar", "path_params": {"x": 1}, "root_path": "/foo/1"}

    @pytest.mark.parametrize(
        ["name", "params", "expected_url", "exception"],
        (
            pytest.param(
                "foo", {"x": 1, "path": "/foo"}, url.URL(scheme="http", path="/foo/1"), None, id="match_full_name"
            ),
            pytest.param("foo:bar", {"x": 1}, url.URL(scheme="http", path="/foo/1/bar"), None, id="match_route"),
            pytest.param(
                "foo:nested",
                {"x": 1, "path": "/foo"},
                url.URL(scheme="http", path="/foo/1/nested"),
                None,
                id="match_nested_app",
            ),
            pytest.param(
                "wrong",
                {"x": 1},
                None,
                exceptions.NotFoundException(params={"x": 1}, name="wrong"),
                id="not_found_mount",
            ),
            pytest.param(
                "foo:wrong",
                {"x": 1},
                None,
                exceptions.NotFoundException(params={"x": 1}, name="wrong"),
                id="not_found_route",
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve_url(self, name, params, expected_url, exception, mount):
        mount.app.add_route("/bar", MagicMock(), name="bar")
        mount.app.mount("/nested", MagicMock(), name="nested")

        with exception:
            assert mount.resolve_url(name, **params) == expected_url

    def test_routes(self, mount):
        route = MagicMock(spec=Route)

        mount.app = MagicMock(spec=Flama)
        mount.app.routes = [route]

        assert mount.routes == [route]


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

    def test_eq(self):
        route = MagicMock(Route)
        assert Router(routes=[route]) == Router(routes=[route])

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    async def test_call_lifespan(self, router, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = "lifespan"

        with patch.object(router, "lifespan", new_callable=AsyncMock) as method_mock:
            await router(asgi_scope, asgi_receive, asgi_send)

        assert method_mock.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    @pytest.mark.parametrize(
        ["request_type"], (pytest.param("http", id="http"), pytest.param("websocket", id="websocket"))
    )
    async def test_call(self, request_type, router, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = request_type

        route = AsyncMock()
        route_scope = types.Scope({})
        with patch.object(router, "resolve_route", return_value=(route, route_scope)):
            await router(asgi_scope, asgi_receive, asgi_send)

        assert route.call_args_list == [call(route_scope, asgi_receive, asgi_send)]

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

        router.mount("/app/", app=Router(components=[component_mock]))

        assert router.components == [component_mock]

    def test_add_component(self, router, component_mock):
        assert router.components == []

        router.add_component(component_mock)

        assert router.components == [component_mock]

    def test_add_route_function(self, router):
        async def foo():
            return "foo"

        router.add_route("/", foo)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo

    def test_add_route_endpoint(self, router):
        class FooEndpoint(endpoints.HTTPEndpoint):
            async def get(self):
                return "foo"

        router.add_route("/", FooEndpoint)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint

    def test_add_route_wrong_params(self, router):
        with pytest.raises(AssertionError, match="Either 'path' and 'endpoint' or 'route' variables are needed"):
            router.add_route()

    def test_add_route_wrong_endpoint(self, router):
        class Foo:
            ...

        with pytest.raises(AssertionError, match="Endpoint must be a callable or an HTTPEndpoint subclass"):
            router.add_route(path="/", endpoint=Foo)

    def test_route_function(self, router):
        @router.route("/")
        async def foo():
            return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo

    def test_route_endpoint(self, router):
        @router.route("/")
        class FooEndpoint(endpoints.HTTPEndpoint):
            async def get(self):
                return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint

    def test_route_wrong_endpoint(self, router):
        with pytest.raises(AssertionError, match="Endpoint must be a callable or an HTTPEndpoint subclass"):

            @router.route("/")
            class Foo:
                ...

    def test_add_websocket_route_function(self, router):
        async def foo():
            return "foo"

        router.add_websocket_route("/", foo)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo

    def test_add_websocket_route_endpoint(self, router):
        class FooEndpoint(endpoints.WebSocketEndpoint):
            async def on_receive(self, websocket):
                return "foo"

        router.add_websocket_route("/", FooEndpoint)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint

    def test_add_websocket_route_wrong_params(self, router):
        with pytest.raises(AssertionError, match="Either 'path' and 'endpoint' or 'route' variables are needed"):
            router.add_websocket_route()

    def test_add_websocket_route_wrong_endpoint(self, router):
        class Foo:
            ...

        with pytest.raises(AssertionError, match="Endpoint must be a callable or a WebSocketEndpoint subclass"):
            router.add_websocket_route(path="/", endpoint=Foo)

    def test_websocket_route_function(self, router):
        @router.websocket_route("/")
        async def foo():
            return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo

    def test_websocket_route_endpoint(self, router):
        @router.websocket_route("/")
        class FooEndpoint(endpoints.WebSocketEndpoint):
            async def on_receive(self, websocket):
                return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint

    def test_websocket_route_wrong_endpoint(self, router):
        with pytest.raises(AssertionError, match="Endpoint must be a callable or a WebSocketEndpoint subclass"):

            @router.websocket_route(path="/")
            class Foo:
                ...

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
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_route.app, Router)
        mount_router = mount_route.app
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
                components=[component_mock],
            ),
            Mount(
                "/bar",
                app=Router(
                    routes=[Route("/", foo, methods=["GET"]), Route("/view", foo_view, methods=["GET"])],
                    components=[component_mock],
                ),
            ),
        ]

        app = Flama(routes=routes, schema=None, docs=None)

        assert len(app.router.routes) == 3

        # Check first-level route is initialized
        assert isinstance(app.router.routes[0], Route)
        root_route = app.router.routes[0]
        assert root_route.path == "/"

        # Check mount with routes is initialized
        assert isinstance(app.router.routes[1], Mount)
        mount_with_routes_route = app.router.routes[1]
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_with_routes_route.app, Router)
        mount_with_routes_router = mount_with_routes_route.app
        assert mount_with_routes_router.components == Components([component_mock])
        # As the component is repeated, it should appear twice
        assert app.components == Components([component_mock, component_mock])
        # Check second-level routes are created an initialized
        assert len(mount_with_routes_route.routes) == 2
        assert mount_with_routes_route.routes[0].path == "/"
        assert mount_with_routes_route.routes[1].path == "/view"

        # Check mount with app is initialized
        assert isinstance(app.router.routes[2], Mount)
        mount_with_app_route = app.router.routes[2]
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_with_app_route.app, Router)
        mount_with_app_router = mount_with_app_route.app
        assert mount_with_app_router.components == Components([component_mock])
        # As the component is repeated, it should appear twice
        assert app.components == Components([component_mock, component_mock])
        # Check second-level routes are created an initialized
        assert len(mount_with_app_route.routes) == 2
        assert mount_with_app_route.routes[0].path == "/"
        assert mount_with_app_route.routes[1].path == "/view"

    def test_resolve_route_route(self, app, asgi_scope):
        @app.route("/foo/")
        async def foo():
            return "foo"

        asgi_scope["path"] = "/foo/"
        asgi_scope["method"] = "GET"

        route, route_scope = app.router.resolve_route(scope=asgi_scope)

        assert route.endpoint == foo
        assert route.path == "/foo/"
        assert route_scope is not None
        assert route_scope["path"] == "/foo/"
        assert route_scope["root_path"] == ""
        assert route_scope["endpoint"] == foo

    def test_resolve_route_mount_view(self, app, router, asgi_scope):
        @router.route("/foo/")
        async def foo():
            return "foo"

        app.mount("/router", app=router)

        asgi_scope["path"] = "/router/foo/"
        asgi_scope["method"] = "GET"

        route, route_scope = app.router.resolve_route(scope=asgi_scope)

        assert route.endpoint == foo
        assert route.path == "/foo/"
        assert route_scope is not None
        assert route_scope["path"] == "/foo/"
        assert route_scope["root_path"] == "/router"
        assert route_scope["endpoint"] == foo

    def test_resolve_route_nested_mount_view(self, app, router, asgi_scope):
        @router.route("/foo/")
        async def foo():
            return "foo"

        app.mount("/router", app=Router(routes=[Mount("/nested", app=router)]))

        asgi_scope["path"] = "/router/nested/foo/"
        asgi_scope["method"] = "GET"

        route, route_scope = app.router.resolve_route(scope=asgi_scope)

        assert route_scope is not None
        assert route.endpoint == foo
        assert route.path == "/foo/"
        assert route_scope["path"] == "/foo/"
        assert route_scope["root_path"] == "/router/nested"
        assert route_scope["endpoint"] == foo

    def test_resolve_route_partial(self, app, asgi_scope):
        @app.route("/foo/")
        async def foo():
            return "foo"

        asgi_scope["path"] = "/foo/"
        asgi_scope["method"] = "POST"

        with pytest.raises(exceptions.MethodNotAllowedException):
            route, route_scope = app.router.resolve_route(scope=asgi_scope)

    def test_resolve_route_not_found(self, app, asgi_scope):
        asgi_scope["path"] = "/foo/"
        asgi_scope["method"] = "GET"

        with pytest.raises(exceptions.NotFoundException):
            route, route_scope = app.router.resolve_route(scope=asgi_scope)

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
