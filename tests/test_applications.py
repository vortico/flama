import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import Component, Module, exceptions, http, routing, types, websockets
from flama.applications import Context, Flama
from flama.ddd.components import WorkerComponent
from flama.events import Events
from flama.injection.injector import Injector
from flama.middleware import Middleware, MiddlewareStack
from flama.models import ModelsModule
from flama.resources import Resource, ResourceRoute, ResourcesModule
from flama.schemas.modules import SchemaModule
from flama.types.applications import AppStatus
from flama.url import URL

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
        assert isinstance(app.app, routing.Router)
        assert isinstance(app.router, routing.Router)
        # Check injector
        assert isinstance(app._injector, Injector)
        assert app._injector._context_cls == Context
        assert app._injector._context_cls.types == {
            "scope": types.Scope,
            "receive": types.Receive,
            "send": types.Send,
            "exc": Exception,
            "app": Flama,
            "route": routing.BaseRoute,
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
        assert app.modules == {*DEFAULT_MODULES, module}
        # Check components
        default_components = app.components[:1]
        assert isinstance(default_components[0], WorkerComponent)
        assert app.components == [*default_components, component_obj]
        # Check events
        assert app.events == Events(
            startup=[m.on_startup for m in app.modules.values()], shutdown=[m.on_shutdown for m in app.modules.values()]
        )

    def test_getattr(self, app):
        for name, module in app.modules.items():
            assert getattr(app, name) == module

        assert getattr(app, "wrong") is None

    @pytest.mark.parametrize(
        ["request_type", "app_status", "exception"],
        (
            pytest.param("http", types.AppStatus.READY, None, id="http_ready"),
            pytest.param(
                "http",
                types.AppStatus.NOT_STARTED,
                exceptions.ApplicationError("Application is not ready to process requests yet."),
                id="http_not_started",
            ),
            pytest.param(
                "http",
                types.AppStatus.SHUT_DOWN,
                exceptions.ApplicationError("Application is already shut down."),
                id="http_shut_down",
            ),
            pytest.param("websocket", types.AppStatus.READY, None, id="websocket_ready"),
            pytest.param(
                "websocket",
                types.AppStatus.NOT_STARTED,
                exceptions.ApplicationError("Application is not ready to process requests yet."),
                id="websocket_not_started",
            ),
            pytest.param(
                "websocket",
                types.AppStatus.SHUT_DOWN,
                exceptions.ApplicationError("Application is already shut down."),
                id="websocket_shut_down",
            ),
            pytest.param("lifespan", types.AppStatus.READY, None, id="lifespan_ready"),
            pytest.param("lifespan", types.AppStatus.NOT_STARTED, None, id="lifespan_not_started"),
            pytest.param("lifespan", types.AppStatus.SHUT_DOWN, None, id="lifespan_shut_down"),
        ),
        indirect=["exception"],
    )
    async def test_call(self, request_type, app_status, exception, app, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["type"] = request_type
        app._status = app_status

        with exception, patch.object(app, "middleware", new=AsyncMock(spec=MiddlewareStack)):
            await app(asgi_scope, asgi_receive, asgi_send)

            assert "app" in asgi_scope
            assert asgi_scope["app"] == app
            assert "root_app" in asgi_scope
            assert asgi_scope["root_app"] == app
            assert app.middleware.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    def test_components(self, app):
        component = MagicMock(spec=Component)

        app.router.add_component(component)

        default_components = app.components[:1]
        assert app.components == [*default_components, component]

    def test_add_component(self, app, component):
        component_obj = component()

        with patch.object(app, "router", spec=routing.Router) as router_mock:
            app.add_component(component_obj)

        assert router_mock.add_component.call_args_list == [call(component_obj)]
        assert router_mock.build.call_args_list == [call(app)]

    def test_routes(self, app):
        expected_routes = [MagicMock()]
        with patch.object(app, "router", spec=routing.Router) as router_mock:
            router_mock.routes = expected_routes
            routes = app.routes

        assert routes == expected_routes

    def test_add_route(self, app, tags):
        def foo(): ...

        with patch.object(app, "router", spec=routing.Router) as router_mock:
            router_mock.add_route.return_value = foo
            route = app.add_route("/", foo, tags=tags)

        assert router_mock.add_route.call_args_list == [
            call(
                "/",
                foo,
                methods=None,
                name=None,
                include_in_schema=True,
                route=None,
                root=app,
                pagination=None,
                tags=tags,
            )
        ]
        assert route == foo

    def test_route(self, app, tags):
        with patch.object(app, "router", spec=routing.Router) as router_mock:

            @app.route("/", tags=tags)
            def foo(): ...

        assert router_mock.route.call_args_list == [
            call("/", methods=None, name=None, include_in_schema=True, root=app, pagination=None, tags=tags)
        ]

    def test_add_websocket_route(self, app, tags):
        def foo(): ...

        with patch.object(app, "router", spec=routing.Router) as router_mock:
            router_mock.add_websocket_route.return_value = foo
            route = app.add_websocket_route("/", foo, tags=tags)

        assert router_mock.add_websocket_route.call_args_list == [
            call("/", foo, name=None, route=None, root=app, pagination=None, tags=tags)
        ]
        assert route == foo

    def test_websocket_route(self, app, tags):
        with patch.object(app, "router", spec=routing.Router) as router_mock:

            @app.websocket_route("/", tags=tags)
            def foo(): ...

        assert router_mock.websocket_route.call_args_list == [
            call("/", name=None, root=app, pagination=None, tags=tags)
        ]

    def test_mount(self, app, tags):
        expected_mount = MagicMock()

        with patch.object(app, "router", spec=routing.Router) as router_mock:
            router_mock.mount.return_value = expected_mount
            mount = app.mount("/", expected_mount, tags=tags)

        assert router_mock.mount.call_args_list == [
            call("/", expected_mount, name=None, mount=None, root=app, tags=tags)
        ]
        assert mount == expected_mount

    def test_injector(self, app):
        assert isinstance(app.injector, Injector)

    def test_add_event_handler(self, app):
        handlers_before = app.events.startup.copy()

        def handler(): ...

        app.add_event_handler("startup", handler)

        assert app.events.startup == [*handlers_before, handler]

    def test_on_event(self, app):
        handlers_before = app.events.startup.copy()

        @app.on_event("startup")
        def handler(): ...

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
            def __init__(self, app: types.App) -> None: ...

            def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send): ...

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
            pytest.param(
                "bar",
                {"x": uuid.UUID(int=1), "y": uuid.UUID(int=2)},
                URL(scheme="http", path=f"/bar/{uuid.UUID(int=1)}/y/{uuid.UUID(int=2)}"),
                None,
                id="multiple_path_params",
            ),
            pytest.param("foo:bar", {}, URL(scheme="http", path="/foo/bar"), None, id="nested"),
            pytest.param(
                "puppy:custom", {}, URL(scheme="http", path="/puppy/custom"), None, id="resource_custom_method"
            ),
            pytest.param(
                "not-found",
                {},
                None,
                exceptions.NotFoundException(name="not-found"),
                id="not_found",
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve_url(self, app, resolve, path_params, resolution, exception):
        app.add_route(route=routing.Route("/foo", lambda: None, name="foo"))
        app.add_route(route=routing.Route("/foo/{x:int}", lambda: None, name="foo"))
        app.add_route(route=routing.Route("/bar/{x:uuid}/y/{y:uuid}", lambda: None, name="bar"))
        app.mount(mount=routing.Mount("/foo", routes=[routing.Route("/bar", lambda: None, name="bar")], name="foo"))

        @app.resources.resource("/puppy")
        class PuppyResource(Resource):
            name = "puppy"
            verbose_name = "Puppy"

            @ResourceRoute.method("/custom")
            def custom(self): ...

        with exception:
            assert app.resolve_url(resolve, **path_params) == resolution

    def test_build_application(self, module):
        root_component = MagicMock(spec=Component)
        root_app = Flama(schema=None, docs=None, components=[root_component])
        root_app.add_get("/foo", lambda: {})

        assert len(root_app.router.routes) == 1
        root_default_components = root_app.components[:1]
        assert root_app.components == [*root_default_components, root_component]
        assert root_app.modules == DEFAULT_MODULES

        leaf_component = MagicMock(spec=Component)
        leaf_app = Flama(schema=None, docs=None, components=[leaf_component], modules={module()})
        leaf_app.add_get("/bar", lambda: {})

        assert len(leaf_app.router.routes) == 1
        leaf_default_components = leaf_app.components[:1]
        assert leaf_app.components == [*leaf_default_components, leaf_component]
        assert leaf_app.modules == [*DEFAULT_MODULES, module]

        root_app.mount("/app", app=leaf_app)

        assert len(root_app.router.routes) == 2
        # Check mount is initialized
        assert isinstance(root_app.routes[1], routing.Mount)
        mount_route = root_app.router.routes[1]
        assert mount_route.path == "/app"
        # Check router is created and initialized
        assert isinstance(mount_route.app, Flama)
        mount_app = mount_route.app
        assert isinstance(mount_app.app, routing.Router)
        mount_router = mount_app.app
        # Check components are collected across the entire tree
        assert root_app.components == [*root_default_components, root_component]
        assert mount_router.components == [*leaf_default_components, leaf_component, *root_app.components]
        # Check modules are isolated for each app
        assert mount_app.modules == [*DEFAULT_MODULES, module]
        assert root_app.modules == DEFAULT_MODULES

    def test_build_application_declarative(self, module):
        leaf_component = MagicMock(spec=Component)
        leaf_routes = [routing.Route("/bar", lambda: {})]
        leaf_app = Flama(routes=leaf_routes, schema=None, docs=None, components=[leaf_component], modules={module()})
        root_component = MagicMock(spec=Component)
        root_routes = [routing.Route("/foo", lambda: {}), routing.Mount("/app", app=leaf_app)]
        root_app = Flama(routes=root_routes, schema=None, docs=None, components=[root_component])

        assert len(root_app.router.routes) == 2
        # Check mount is initialized
        assert isinstance(root_app.routes[1], routing.Mount)
        mount_route = root_app.router.routes[1]
        assert mount_route.path == "/app"
        # Check router is created and initialized
        assert isinstance(mount_route.app, Flama)
        mount_app = mount_route.app
        assert isinstance(mount_app.app, routing.Router)
        mount_router = mount_app.app
        # Check components are collected across the entire tree
        root_default_components = root_app.components[:1]
        assert root_app.components == [*root_default_components, root_component]
        leaf_default_components = leaf_app.components[:1]
        assert mount_router.components == [*leaf_default_components, leaf_component, *root_app.components]
        # Check modules are isolated for each app
        assert mount_app.modules == [*DEFAULT_MODULES, module]
        assert root_app.modules == DEFAULT_MODULES

    async def test_call_complete_workflow(self):
        receive_queue = asyncio.Queue()
        send_queue = asyncio.Queue()

        async def receive() -> types.Message:
            return await receive_queue.get()

        async def send(message: types.Message) -> None:
            await send_queue.put(message)

        app = Flama(docs=None, schema=None)
        sub_app = Flama(docs=None, schema=None)
        sub_app.add_route("/bar/", lambda: {"foo": "bar"})
        app.mount("/foo", sub_app)

        assert app._status == AppStatus.NOT_STARTED
        assert sub_app._status == AppStatus.NOT_STARTED

        await receive_queue.put(types.Message({"type": "lifespan.startup"}))
        await app(types.Scope({"type": "lifespan"}), receive, send)
        assert await send_queue.get() == {"type": "lifespan.startup.complete"}

        assert app._status == AppStatus.READY
        assert sub_app._status == AppStatus.READY

        await app(types.Scope({"type": "http", "path": "/foo/bar/", "method": "GET"}), receive, send)
        assert await send_queue.get() == {
            "type": "http.response.start",
            "headers": [(b"content-length", b"13"), (b"content-type", b"application/json")],
            "status": 200,
        }
        assert await send_queue.get() == {"body": b'{"foo":"bar"}', "type": "http.response.body"}

        await receive_queue.put(types.Message({"type": "lifespan.shutdown"}))
        await app(types.Scope({"type": "lifespan"}), receive, send)
        assert await send_queue.get() == {"type": "lifespan.shutdown.complete"}

        assert app._status == AppStatus.SHUT_DOWN
        assert sub_app._status == AppStatus.SHUT_DOWN
