import functools
import typing

from starlette.applications import Starlette
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware

from flama.exceptions import HTTPException
from flama.injection import Injector
from flama.lifespan import Lifespan
from flama.modules import Modules
from flama.pagination import paginator
from flama.resources import ResourcesModule
from flama.responses import APIErrorResponse
from flama.routing import Router
from flama.schemas.modules import SchemaModule
from flama.sqlalchemy import SQLAlchemyModule

if typing.TYPE_CHECKING:
    from starlette.middleware import Middleware
    from starlette.types import ASGIApp

    from flama.components import Component, Components
    from flama.http import Request, Response
    from flama.modules import Module
    from flama.routing import BaseRoute, Mount

__all__ = ["Flama"]


DEFAULT_MODULES = [SQLAlchemyModule, ResourcesModule, SchemaModule]


class Flama(Starlette):
    def __init__(
        self,
        routes: typing.Sequence[typing.Union["BaseRoute", "Mount"]] = None,
        components: typing.Optional[typing.List["Component"]] = None,
        modules: typing.Optional[typing.List["Module"]] = None,
        middleware: typing.Sequence["Middleware"] = None,
        debug: bool = False,
        on_startup: typing.Sequence[typing.Callable] = None,
        on_shutdown: typing.Sequence[typing.Callable] = None,
        lifespan: typing.Callable[["Flama"], typing.AsyncContextManager] = None,
        sqlalchemy_database: typing.Optional[str] = None,
        title: typing.Optional[str] = "",
        version: typing.Optional[str] = "",
        description: typing.Optional[str] = "",
        schema: typing.Optional[str] = "/schema/",
        docs: typing.Optional[str] = "/docs/",
        redoc: typing.Optional[str] = None,
        *args,
        **kwargs
    ) -> None:
        super().__init__(debug, *args, **kwargs)

        # Initialize router and middleware stack
        self.router = Router(
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
                    "redoc": redoc,
                },
                **kwargs,
            },
        )

        # Reference to paginator from within app
        self.paginator = paginator

    def __getattr__(self, item: str) -> "Module":
        return self.modules.__getattr__(item)

    @property
    def injector(self) -> Injector:
        return Injector(self.components)

    @property
    def components(self) -> "Components":
        return self.router.components

    def mount(self, path: str, app: "ASGIApp", name: str = None) -> None:
        self.router.mount(path, app=app, name=name)

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
