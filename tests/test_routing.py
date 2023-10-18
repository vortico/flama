from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import endpoints, exceptions, types, url, websockets
from flama.applications import Flama
from flama.client import AsyncClient
from flama.endpoints import HTTPEndpoint, WebSocketEndpoint
from flama.injection import Component, Components
from flama.lifespan import Lifespan
from flama.routing import BaseRoute, EndpointWrapper, Match, Mount, Route, Router, WebSocketRoute


class TestCaseBaseRoute:
    @pytest.fixture(scope="function")
    def route_cls(self):
        class _Route(BaseRoute):
            async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
                return await self.handle(scope, receive, send)

        return _Route

    @pytest.fixture(scope="function")
    def route(self, route_cls):
        return route_cls(
            "/", EndpointWrapper(lambda: None, EndpointWrapper.type.http), name="foo", include_in_schema=False
        )

    def test_init(self, route_cls):
        def foo():
            ...

        app = EndpointWrapper(foo, EndpointWrapper.type.http)
        route = route_cls(
            "/",
            app,
            name="foo",
            include_in_schema=False,
            tags={"tag": "tag", "list_tag": ["foo", "bar"], "dict_tag": {"foo": "bar"}},
        )

        assert route.path == url.RegexPath("/")
        assert route.app == app
        assert route.endpoint == foo
        assert route.name == "foo"
        assert route.include_in_schema is False
        assert route.tags == {"tag": "tag", "list_tag": ["foo", "bar"], "dict_tag": {"foo": "bar"}}

    def test_eq(self, route_cls):
        def foo():
            ...

        assert route_cls("/", foo, name="foo") == route_cls("/", foo, name="foo")
        assert route_cls("/", foo, name="foo") != route_cls("/", foo, name="bar")

    def test_repr(self, route_cls):
        def foo():
            ...

        assert repr(route_cls("/", foo, name="foo")) == "_Route(path='/', name='foo')"

    @pytest.mark.parametrize(["app"], (pytest.param(MagicMock(spec=Flama), id="app"), pytest.param(None, id="no_app")))
    def test_build(self, app, route):
        expected_calls = [call(app)] if app else []
        with patch.object(route, "parameters") as parameters_mock:
            route.build(app)

        assert parameters_mock.build.call_args_list == expected_calls

    def test_endpoint_handlers(self, route):
        assert route.endpoint_handlers() == {}

    async def test_handle(self, route_cls, asgi_scope, asgi_receive, asgi_send):
        app = AsyncMock()
        route = route_cls("/", app)

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

    def test_route_scope(self, route_cls, asgi_scope):
        app = AsyncMock()
        route = route_cls("/", app)
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
    def test_resolve_url(self, route_cls, name, params, exception):
        route = route_cls("/foo/{bar:int}", lambda bar: None, name="foo")

        with exception:
            assert route.resolve_url(name=name, **params)


class TestCaseRoute:
    @pytest.fixture(scope="function")
    def route(self):
        return Route("/", EndpointWrapper(lambda: None, EndpointWrapper.type.http), name="foo", include_in_schema=False)

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

    @pytest.mark.parametrize(
        ["scope_type", "handle_call"],
        (
            pytest.param("http", True, id="http"),
            pytest.param("websocket", False, id="websocket"),
            pytest.param("lifespan", False, id="lifespan"),
            pytest.param("wrong", False, id="wrong"),
        ),
    )
    async def test_call(self, scope_type, handle_call, route, asgi_scope, asgi_receive, asgi_send):
        scope = types.Scope({**asgi_scope, "type": scope_type})
        route_scope = types.Scope({"foo": "bar"})
        handle = AsyncMock()
        expected_calls = [call(types.Scope({**scope, **route_scope}), asgi_receive, asgi_send)] if handle_call else []

        with patch.object(route, "handle", new=handle), patch.object(route, "route_scope", return_value=route_scope):
            await route(scope, asgi_receive, asgi_send)

        assert handle.call_args_list == expected_calls

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
    def route(self):
        return WebSocketRoute(
            "/", EndpointWrapper(lambda: None, EndpointWrapper.type.websocket), name="foo", include_in_schema=False
        )

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

    @pytest.mark.parametrize(
        ["scope_type", "handle_call"],
        (
            pytest.param("http", False, id="http"),
            pytest.param("websocket", True, id="websocket"),
            pytest.param("lifespan", False, id="lifespan"),
            pytest.param("wrong", False, id="wrong"),
        ),
    )
    async def test_call(self, scope_type, handle_call, route, asgi_scope, asgi_receive, asgi_send):
        scope = types.Scope({**asgi_scope, "type": scope_type})
        route_scope = types.Scope({"foo": "bar"})
        handle = AsyncMock()
        expected_calls = [call(types.Scope({**scope, **route_scope}), asgi_receive, asgi_send)] if handle_call else []

        with patch.object(route, "handle", new=handle), patch.object(route, "route_scope", return_value=route_scope):
            await route(scope, asgi_receive, asgi_send)

        assert handle.call_args_list == expected_calls

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

    @pytest.mark.parametrize(
        ["scope_type", "handle_call"],
        (
            pytest.param("http", True, id="http"),
            pytest.param("websocket", True, id="websocket"),
            pytest.param("lifespan", True, id="lifespan"),
            pytest.param("wrong", False, id="wrong"),
        ),
    )
    async def test_call(self, scope_type, handle_call, mount, asgi_scope, asgi_receive, asgi_send):
        scope = types.Scope({**asgi_scope, "type": scope_type})
        route_scope = types.Scope({"foo": "bar"})
        handle = AsyncMock()
        expected_calls = [call(types.Scope({**scope, **route_scope}), asgi_receive, asgi_send)] if handle_call else []

        with patch.object(mount, "handle", new=handle), patch.object(mount, "route_scope", return_value=route_scope):
            await mount(scope, asgi_receive, asgi_send)

        assert handle.call_args_list == expected_calls

    def test_eq(self, app):
        assert Mount("/", app, name="app_mock") == Mount("/", app, name="app_mock")
        assert Mount("/", app, name="app_mock") != Mount("/", app, name="bar")

    @pytest.mark.parametrize(
        ["app", "used"],
        (
            pytest.param(MagicMock(spec=Router), False, id="router"),
            pytest.param(MagicMock(spec=Flama, router=MagicMock(spec=Router, components=[])), True, id="app"),
        ),
    )
    def test_build(self, mount, app, used):
        root_app = MagicMock(spec=Flama)
        expected_calls = [call(app)] if used else [call(root_app)]

        route = MagicMock(spec=Route)
        mount.app = app
        mount.app.routes = [route]

        mount.build(root_app)

        assert route.build.call_args_list == expected_calls

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

    async def test_handle(self, mount, asgi_scope, asgi_receive, asgi_send):
        mount = Mount("/", AsyncMock(spec=Flama))

        await mount.handle(asgi_scope, asgi_receive, asgi_send)

        assert mount.app.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    @pytest.mark.parametrize(
        ["app", "used"],
        (
            pytest.param(Router(), False, id="router"),
            pytest.param(Flama(docs=None, schema=None), True, id="app"),
        ),
    )
    def test_route_scope(self, mount, asgi_scope, app, used):
        def bar():
            ...

        mount.app = app
        mount.app.add_route("/bar", bar)

        asgi_scope["path"] = "/foo/1/bar"
        route_scope = mount.route_scope(asgi_scope)

        assert route_scope == {
            "app": app if used else asgi_scope["app"],
            "endpoint": mount.app,
            "path": "/bar",
            "path_params": {"x": 1},
            "root_path": "" if used else "/foo/1",
        }

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

    def test_add_route_function(self, router, tags):
        async def foo():
            return "foo"

        router.add_route("/", foo, tags=tags)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo
        assert router.routes[0].tags == tags

    def test_add_route_endpoint(self, router, tags):
        class FooEndpoint(endpoints.HTTPEndpoint):
            async def get(self):
                return "foo"

        router.add_route("/", FooEndpoint, tags=tags)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint
        assert router.routes[0].tags == tags

    def test_add_route_wrong_params(self, router):
        with pytest.raises(AssertionError, match="Either 'path' and 'endpoint' or 'route' variables are needed"):
            router.add_route()

    def test_add_route_wrong_endpoint(self, router):
        class Foo:
            ...

        with pytest.raises(AssertionError, match="Endpoint must be a callable or an HTTPEndpoint subclass"):
            router.add_route(path="/", endpoint=Foo)

    def test_route_function(self, router, tags):
        @router.route("/", tags=tags)
        async def foo():
            return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo
        assert router.routes[0].tags == tags

    def test_route_endpoint(self, router, tags):
        @router.route("/", tags=tags)
        class FooEndpoint(endpoints.HTTPEndpoint):
            async def get(self):
                return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint
        assert router.routes[0].tags == tags

    def test_route_wrong_endpoint(self, router):
        with pytest.raises(AssertionError, match="Endpoint must be a callable or an HTTPEndpoint subclass"):

            @router.route("/")
            class Foo:
                ...

    def test_add_websocket_route_function(self, router, tags):
        async def foo():
            return "foo"

        router.add_websocket_route("/", foo, tags=tags)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo
        assert router.routes[0].tags == tags

    def test_add_websocket_route_endpoint(self, router, tags):
        class FooEndpoint(endpoints.WebSocketEndpoint):
            async def on_receive(self, websocket):
                return "foo"

        router.add_websocket_route("/", FooEndpoint, tags=tags)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint
        assert router.routes[0].tags == tags

    def test_add_websocket_route_wrong_params(self, router):
        with pytest.raises(AssertionError, match="Either 'path' and 'endpoint' or 'route' variables are needed"):
            router.add_websocket_route()

    def test_add_websocket_route_wrong_endpoint(self, router):
        class Foo:
            ...

        with pytest.raises(AssertionError, match="Endpoint must be a callable or a WebSocketEndpoint subclass"):
            router.add_websocket_route(path="/", endpoint=Foo)

    def test_websocket_route_function(self, router, tags):
        @router.websocket_route("/", tags=tags)
        async def foo():
            return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == foo
        assert router.routes[0].tags == tags

    def test_websocket_route_endpoint(self, router, tags):
        @router.websocket_route("/", tags=tags)
        class FooEndpoint(endpoints.WebSocketEndpoint):
            async def on_receive(self, websocket):
                return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint
        assert router.routes[0].tags == tags

    def test_websocket_route_wrong_endpoint(self, router):
        with pytest.raises(AssertionError, match="Endpoint must be a callable or a WebSocketEndpoint subclass"):

            @router.websocket_route(path="/")
            class Foo:
                ...

    def test_mount_app(self, app, app_mock, tags):
        app.mount("/app/", app=app_mock, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], Mount)
        assert app.routes[0].path == "/app"
        assert app.routes[0].app == app_mock
        assert app.routes[0].tags == tags

    def test_mount_router(self, app, component_mock, tags):
        router = Router(components=[component_mock])

        app.mount("/app/", app=router, tags=tags)

        assert len(app.router.routes) == 1
        # Check mount is initialized
        assert isinstance(app.routes[0], Mount)
        mount_route = app.router.routes[0]
        assert mount_route.path == "/app"
        assert mount_route.tags == tags
        # Check router is created and initialized, also shares components and modules with main app
        assert isinstance(mount_route.app, Router)
        mount_router = mount_route.app
        default_components = app.components[:1]
        assert mount_router.components == [component_mock]
        assert app.components == default_components

    def test_mount_declarative(self, component_mock, tags):
        def root():
            ...

        def foo():
            ...

        def foo_view():
            ...

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

    def test_resolve_route_mount_app(self, app, asgi_scope):
        nested = Flama()

        @nested.route("/foo/")
        async def foo():
            return "foo"

        app.mount("/router", app=nested)

        asgi_scope["path"] = "/router/foo/"
        asgi_scope["method"] = "GET"

        route, route_scope = app.router.resolve_route(scope=asgi_scope)

        assert route.endpoint == foo
        assert route.path == "/foo/"
        assert route_scope is not None
        assert route_scope["path"] == "/foo/"
        assert route_scope["root_path"] == ""
        assert route_scope["endpoint"] == foo

    def test_resolve_route_mount_router(self, app, router, asgi_scope):
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

    def test_resolve_route_nested_mount_router(self, app, router, asgi_scope):
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

    async def test_request_nested_app(self, app):
        sub_app = Flama(docs=None, schema=None)
        sub_app.add_route("/bar/", lambda: {"foo": "bar"}, ["GET"])

        app.mount("/foo", sub_app)

        async with AsyncClient(app) as client:
            response = await client.get("/foo/bar/")
            assert response.status_code == 200
            assert response.json() == {"foo": "bar"}
