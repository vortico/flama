import functools
import typing

from starlette.applications import Starlette
from starlette.middleware.exceptions import ExceptionMiddleware

from flama.debug.middleware import ServerErrorMiddleware
from flama.exceptions import HTTPException
from flama.injection import Injector
from flama.lifespan import Lifespan
from flama.middleware import Middleware
from flama.models.modules import ModelsModule
from flama.modules import Modules
from flama.pagination import paginator
from flama.resources import ResourcesModule
from flama.responses import APIErrorResponse
from flama.routing import Router
from flama.schemas.modules import SchemaModule
from flama.sqlalchemy import SQLAlchemyModule

if typing.TYPE_CHECKING:
    from flama.asgi import App
    from flama.components import Component, Components
    from flama.http import Request, Response
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
        middleware: typing.Sequence["Middleware"] = None,
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
        super().__init__(debug, *args, **kwargs)

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
        self.exception_middleware = ExceptionMiddleware(self.router, debug=debug)
        self.error_middleware = ServerErrorMiddleware(self.exception_middleware, debug=debug)
        self.user_middleware = [] if middleware is None else list(middleware)
        self.middleware_stack = self.build_middleware_stack()

        # Add exception handler for API exceptions
        self.add_exception_handler(HTTPException, self.api_http_exception_handler)

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
        try:
            return self.modules.__getattr__(item)
        except KeyError:
            return None  # type: ignore[return-value]

    def add_route(  # type: ignore[override]
        self,
        path: typing.Optional[str] = None,
        endpoint: typing.Optional[typing.Callable] = None,
        methods: typing.Optional[typing.List[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: bool = True,
        route: typing.Optional["BaseRoute"] = None,
    ) -> None:  # pragma: no cover
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
        self.router.add_websocket_route(path, endpoint, name=name, route=route)

    @property
    def injector(self) -> Injector:
        return Injector(self.components)

    @property
    def components(self) -> "Components":
        return self.router.components

    def add_component(self, component: "Component"):
        self.router.add_component(component)

    @property
    def routes(self) -> typing.List["BaseRoute"]:  # type: ignore[override]
        return self.router.routes

    def mount(self, path: str, app: "App", name: str = None) -> None:  # type: ignore[override]
        self.router.mount(path, app=app, name=name)

    def build_middleware_stack(self) -> "App":  # type: ignore[override]
        debug = self.debug

        middleware = (
            [Middleware(ServerErrorMiddleware, debug=debug)]
            + self.user_middleware
            + [Middleware(ExceptionMiddleware, handlers=self.exception_handlers, debug=debug)]
        )

        app = self.router
        for cls, options in reversed(middleware):
            app = cls(app=app, **options)
        return app

    def api_http_exception_handler(self, request: "Request", exc: HTTPException) -> "Response":
        return APIErrorResponse(detail=exc.detail, status_code=exc.status_code, exception=exc)

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
