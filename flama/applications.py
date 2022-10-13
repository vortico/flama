import functools
import typing

from starlette.applications import Starlette
from starlette.datastructures import State

from flama.injection import Injector
from flama.lifespan import Lifespan
from flama.middleware import Middleware, MiddlewareStack
from flama.models.modules import ModelsModule
from flama.modules import Modules
from flama.pagination import paginator
from flama.resources import ResourcesModule
from flama.routing import Router
from flama.schemas.modules import SchemaModule
from flama.sqlalchemy import SQLAlchemyModule

if typing.TYPE_CHECKING:
    from flama.asgi import App, Receive, Scope, Send
    from flama.components import Component, Components
    from flama.modules import Module
    from flama.routing import BaseRoute, Mount, WebSocketRoute

__all__ = ["Flama"]


DEFAULT_MODULES: typing.List[typing.Type["Module"]] = [SQLAlchemyModule, ResourcesModule, SchemaModule, ModelsModule]


class Flama(Starlette):
    def __init__(
        self,
        routes: typing.Sequence[typing.Union["BaseRoute", "Mount"]] = None,
        components: typing.Optional[typing.List["Component"]] = None,
        modules: typing.Optional[typing.List[typing.Type["Module"]]] = None,
        middleware: typing.Optional[typing.Sequence["Middleware"]] = None,
        debug: bool = False,
        on_startup: typing.Sequence[typing.Callable] = None,
        on_shutdown: typing.Sequence[typing.Callable] = None,
        lifespan: typing.Callable[["Flama"], typing.AsyncContextManager] = None,
        sqlalchemy_database: typing.Optional[str] = None,
        title: typing.Optional[str] = "Flama",
        version: typing.Optional[str] = "0.1.0",
        description: typing.Optional[str] = "Firing up with the flame",
        schema: typing.Optional[str] = "/schema/",
        docs: typing.Optional[str] = "/docs/",
        schema_library: typing.Optional[str] = None,
        *args,
        **kwargs
    ) -> None:
        self._debug = debug
        self.state = State()

        # Initialize router and middleware stack
        self.router: Router = Router(
            main_app=self,
            routes=routes,
            components=components,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            lifespan=Lifespan(self, lifespan),
        )
        self.app = self.router

        self.middleware = MiddlewareStack(app=self.app, middleware=middleware or [], debug=debug)

        # Initialize Modules
        self.modules = Modules(
            [*DEFAULT_MODULES, *(modules or [])],
            self,
            *args,
            **{
                **{
                    "debug": debug,
                    "sqlalchemy_database": sqlalchemy_database,
                    "title": title,
                    "version": version,
                    "description": description,
                    "schema": schema,
                    "docs": docs,
                },
                **kwargs,
            },
        )

        # Setup schema library
        self.modules.schema.set_schema_library(schema_library)  # type: ignore[attr-defined]

        # Reference to paginator from within app
        self.paginator = paginator

    def __getattr__(self, item: str) -> "Module":
        """Retrieve a module by its name.

        :param item: Module name.
        :return: Module.
        """
        try:
            return self.modules.__getattr__(item)
        except KeyError:
            return None  # type: ignore[return-value]

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        """Perform a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive event.
        :param send: ASGI send event.
        """
        scope["app"] = self
        await self.middleware(scope, receive, send)

    def add_route(  # type: ignore[override]
        self,
        path: typing.Optional[str] = None,
        endpoint: typing.Optional[typing.Callable] = None,
        methods: typing.Optional[typing.List[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: bool = True,
        route: typing.Optional["BaseRoute"] = None,
    ) -> None:  # pragma: no cover
        """Register a new HTTP route or endpoint under given path.

        :param path: URL path.
        :param endpoint: HTTP endpoint.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param route: HTTP route.
        """
        self.router.add_route(
            path, endpoint, methods=methods, name=name, include_in_schema=include_in_schema, route=route
        )

    def add_websocket_route(  # type: ignore[override]
        self,
        path: typing.Optional[str] = None,
        endpoint: typing.Optional[typing.Callable] = None,
        name: typing.Optional[str] = None,
        route: typing.Optional["WebSocketRoute"] = None,
    ) -> None:  # pragma: no cover
        """Register a new websocket route or endpoint under given path.

        :param path: URL path.
        :param endpoint: Websocket endpoint.
        :param name: Endpoint or route name.
        :param route: Websocket route.
        """
        self.router.add_websocket_route(path, endpoint, name=name, route=route)

    @property
    def injector(self) -> Injector:
        """Components dependency injector.

        :return: Injector instance.
        """
        return Injector(self.components)

    @property
    def components(self) -> "Components":
        """Components register.

        :return: Components register.
        """
        return self.router.components

    def add_component(self, component: "Component"):
        """Add a new component to the register.

        :param component: Component to include.
        """
        self.router.add_component(component)

    @property
    def routes(self) -> typing.List["BaseRoute"]:  # type: ignore[override]
        """List of registered routes.

        :return: Routes.
        """
        return self.router.routes

    def mount(self, path: str, app: "App", name: str = None) -> None:  # type: ignore[override]
        """Mount a new ASGI application under given path.

        :param path: URL path.
        :param app: ASGI application.
        :param name: Application name.
        """
        self.router.mount(path, app=app, name=name)

    def add_exception_handler(
        self, exc_class_or_status_code: typing.Union[int, typing.Type[Exception]], handler: typing.Callable
    ):
        """Add a new exception handler for given status code or exception class.

        :param exc_class_or_status_code: Status code or exception class.
        :param handler: Exception handler.
        """
        self.middleware.add_exception_handler(exc_class_or_status_code, handler)

    def add_middleware(self, middleware_class: typing.Type, **options: typing.Any):
        """Add a new middleware to the stack.

        :param middleware_class: Middleware class.
        :param options: Keyword arguments used to initialise middleware.
        """
        self.middleware.add_middleware(Middleware(middleware_class, **options))

    get = functools.partialmethod(Starlette.route, methods=["GET"])
    head = functools.partialmethod(Starlette.route, methods=["HEAD"])
    post = functools.partialmethod(Starlette.route, methods=["POST"])
    put = functools.partialmethod(Starlette.route, methods=["PUT"])
    delete = functools.partialmethod(Starlette.route, methods=["DELETE"])
    connect = functools.partialmethod(Starlette.route, methods=["CONNECT"])
    options = functools.partialmethod(Starlette.route, methods=["OPTIONS"])
    trace = functools.partialmethod(Starlette.route, methods=["TRACE"])
    patch = functools.partialmethod(Starlette.route, methods=["PATCH"])
    add_get = functools.partialmethod(Starlette.add_route, methods=["GET"])
    add_head = functools.partialmethod(Starlette.add_route, methods=["HEAD"])
    add_post = functools.partialmethod(Starlette.add_route, methods=["POST"])
    add_put = functools.partialmethod(Starlette.add_route, methods=["PUT"])
    add_delete = functools.partialmethod(Starlette.add_route, methods=["DELETE"])
    add_connect = functools.partialmethod(Starlette.add_route, methods=["CONNECT"])
    add_options = functools.partialmethod(Starlette.add_route, methods=["OPTIONS"])
    add_trace = functools.partialmethod(Starlette.add_route, methods=["TRACE"])
    add_patch = functools.partialmethod(Starlette.add_route, methods=["PATCH"])
