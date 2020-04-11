from unittest.mock import Mock

import pytest
from starlette.routing import Mount

from flama.applications import Flama
from flama.components import Component
from flama.endpoints import HTTPEndpoint, WebSocketEndpoint
from flama.resources import CRUDResource
from flama.routing import Route, Router, WebSocketRoute


class TestCaseRouter:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None)

    @pytest.fixture(scope="function")
    def router(self):
        return Router()

    @pytest.fixture(scope="function")
    def app_mock(self):
        return Mock(spec=Flama)

    @pytest.fixture(scope="function")
    def component_mock(self):
        return Mock(spec=Component)

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
        class FooEndpoint(HTTPEndpoint):
            async def get(self):
                return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Route)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint

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
        class FooEndpoint(WebSocketEndpoint):
            async def on_receive(self, websocket):
                return "foo"

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], WebSocketRoute)
        assert router.routes[0].path == "/"
        assert router.routes[0].endpoint == FooEndpoint

    def test_add_resource(self, router, database, model, schema):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=CRUDResource):
            database = database_
            name = "puppy"
            model = model_
            schema = schema_

        resource = PuppyResource()
        router.add_resource("/", resource)

        assert len(router.routes) == 4
        assert [(route.path, route.methods, route.endpoint) for route in router.routes] == [
            ("/puppy/", {"POST"}, resource.create),
            ("/puppy/{element_id}/", {"GET", "HEAD"}, resource.retrieve),
            ("/puppy/{element_id}/", {"PUT"}, resource.update),
            ("/puppy/{element_id}/", {"DELETE"}, resource.delete),
        ]

    def test_add_resource_decorator(self, router, database, model, schema):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=CRUDResource):
            database = database_
            name = "puppy"
            model = model_
            schema = schema_

        resource = router.resource("/")(PuppyResource())  # Apply decoration to an instance in order to check endpoints

        assert len(router.routes) == 4
        assert [(route.path, route.methods, route.endpoint) for route in router.routes] == [
            ("/puppy/", {"POST"}, resource.create),
            ("/puppy/{element_id}/", {"GET", "HEAD"}, resource.retrieve),
            ("/puppy/{element_id}/", {"PUT"}, resource.update),
            ("/puppy/{element_id}/", {"DELETE"}, resource.delete),
        ]

    def test_mount_app(self, router, app_mock):
        router.mount("/app/", app=app_mock)

        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Mount)
        assert router.routes[0].path == "/app"
        assert router.routes[0].app == app_mock

    def test_mount_router(self, router, component_mock):
        router.components = [component_mock]

        app = Router()

        router.mount("/app/", app=app)
        assert len(router.routes) == 1
        assert isinstance(router.routes[0], Mount)
        assert router.routes[0].path == "/app"
        assert router.routes[0].app == app
        assert router.routes[0].app.components == [component_mock]

    def test_get_route_from_scope_route(self, app, scope):
        @app.route("/foo/")
        async def foo():
            return "foo"

        scope["path"] = "/foo/"
        scope["method"] = "GET"

        route, route_scope = app.router.get_route_from_scope(scope=scope)

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

        scope["path"] = "/foo/"
        scope["root_path"] = "/router"
        scope["method"] = "GET"

        route, route_scope = app.router.get_route_from_scope(scope=scope)

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

        app.mount("/router", app=Router(routes=[Mount('/nested', app=router)]))

        scope["path"] = "/router/nested/foo/"
        scope["method"] = "GET"

        route, route_scope = app.router.get_route_from_scope(scope=scope)

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

        route, route_scope = app.router.get_route_from_scope(scope=scope)

        assert route.endpoint == foo
        assert route.path == "/foo/"
        assert route_scope is not None
        assert route_scope["path"] == "/foo/"
        assert route_scope["root_path"] == ""
        assert route_scope["endpoint"] == foo

    def test_get_route_from_scope_not_found(self, app, scope):
        scope["path"] = "/foo/"
        scope["method"] = "GET"

        route, route_scope = app.router.get_route_from_scope(scope=scope)

        assert route == app.router.not_found
        assert route_scope is None
