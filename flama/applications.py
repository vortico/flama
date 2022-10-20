import functools
import typing as t

from starlette.applications import Starlette
from starlette.datastructures import State

from flama import types
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

if t.TYPE_CHECKING:
    from flama.components import Component, Components
    from flama.modules import Module
    from flama.routing import BaseRoute, Mount, WebSocketRoute

__all__ = ["Flama"]


DEFAULT_MODULES: t.List[t.Type["Module"]] = [SQLAlchemyModule, ResourcesModule, SchemaModule, ModelsModule]


class Flama(Starlette):
    def __init__(
        self,
        routes: t.Sequence[t.Union["BaseRoute", "Mount"]] = None,
        components: t.Optional[t.List["Component"]] = None,
        modules: t.Optional[t.List[t.Type["Module"]]] = None,
        middleware: t.Optional[t.Sequence["Middleware"]] = None,
        debug: bool = False,
        on_startup: t.Sequence[t.Callable] = None,
        on_shutdown: t.Sequence[t.Callable] = None,
        lifespan: t.Callable[["Flama"], t.AsyncContextManager] = None,
        sqlalchemy_database: t.Optional[str] = None,
        title: t.Optional[str] = "Flama",
        version: t.Optional[str] = "0.1.0",
        description: t.Optional[str] = "Firing up with the flame",
        schema: t.Optional[str] = "/schema/",
        docs: t.Optional[str] = "/docs/",
        schema_library: t.Optional[str] = None,
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

        self.middlewares = MiddlewareStack(app=self.app, middleware=middleware or [], debug=debug)

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

    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        """Perform a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive event.
        :param send: ASGI send event.
        """
        scope["app"] = self
        await self.middlewares(scope, receive, send)

    def add_route(  # type: ignore[override]
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[t.Callable] = None,
        methods: t.Optional[t.List[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        route: t.Optional["BaseRoute"] = None,
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

    def route(  # type: ignore[override]
        self, path: str, methods: t.List[str] = None, name: str = None, include_in_schema: bool = True
    ) -> t.Callable:  # pragma: no cover
        """Decorator version for registering a new HTTP route in this router under given path.

        :param path: URL path.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :return: Decorated route.
        """
        return self.router.route(path, methods=methods, name=name, include_in_schema=include_in_schema)

    def add_websocket_route(  # type: ignore[override]
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[t.Callable] = None,
        name: t.Optional[str] = None,
        route: t.Optional["WebSocketRoute"] = None,
    ) -> None:  # pragma: no cover
        """Register a new websocket route or endpoint under given path.

        :param path: URL path.
        :param endpoint: Websocket endpoint.
        :param name: Endpoint or route name.
        :param route: Websocket route.
        """
        self.router.add_websocket_route(path=path, endpoint=endpoint, name=name, route=route)

    def websocket_route(self, path: str, name: str = None) -> t.Callable:  # type: ignore[override]  # pragma: no cover
        """Decorator version for registering a new websocket route in this router under given path.

        :param path: URL path.
        :param name: Websocket route name.
        :return: Decorated route.
        """
        return self.router.websocket_route(path, name=name)

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
    def routes(self) -> t.List["BaseRoute"]:  # type: ignore[override]
        """List of registered routes.

        :return: Routes.
        """
        return self.router.routes

    def mount(self, path: str, app: types.App, name: str = None) -> None:  # type: ignore[override]
        """Mount a new ASGI application under given path.

        :param path: URL path.
        :param app: ASGI application.
        :param name: Application name.
        """
        self.router.mount(path, app=app, name=name)

    def add_exception_handler(self, exc_class_or_status_code: t.Union[int, t.Type[Exception]], handler: t.Callable):
        """Add a new exception handler for given status code or exception class.

        :param exc_class_or_status_code: Status code or exception class.
        :param handler: Exception handler.
        """
        self.middlewares.add_exception_handler(exc_class_or_status_code, handler)

    def add_middleware(self, middleware_class: t.Type, **options: t.Any):
        """Add a new middleware to the stack.

        :param middleware_class: Middleware class.
        :param options: Keyword arguments used to initialise middleware.
        """
        self.middlewares.add_middleware(Middleware(middleware_class, **options))

    get = functools.partialmethod(route, methods=["GET"])
    head = functools.partialmethod(route, methods=["HEAD"])
    post = functools.partialmethod(route, methods=["POST"])
    put = functools.partialmethod(route, methods=["PUT"])
    delete = functools.partialmethod(route, methods=["DELETE"])
    connect = functools.partialmethod(route, methods=["CONNECT"])
    options = functools.partialmethod(route, methods=["OPTIONS"])
    trace = functools.partialmethod(route, methods=["TRACE"])
    patch = functools.partialmethod(route, methods=["PATCH"])
    add_get = functools.partialmethod(add_route, methods=["GET"])
    add_head = functools.partialmethod(add_route, methods=["HEAD"])
    add_post = functools.partialmethod(add_route, methods=["POST"])
    add_put = functools.partialmethod(add_route, methods=["PUT"])
    add_delete = functools.partialmethod(add_route, methods=["DELETE"])
    add_connect = functools.partialmethod(add_route, methods=["CONNECT"])
    add_options = functools.partialmethod(add_route, methods=["OPTIONS"])
    add_trace = functools.partialmethod(add_route, methods=["TRACE"])
    add_patch = functools.partialmethod(add_route, methods=["PATCH"])
