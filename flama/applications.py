import functools
import typing

import anyio
from starlette.applications import Starlette
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.types import ASGIApp

from flama.components import Components
from flama.database import DatabaseModule
from flama.exceptions import HTTPException
from flama.http import Request, Response
from flama.injection import Injector
from flama.modules import Modules
from flama.resources import ResourcesModule
from flama.responses import APIErrorResponse
from flama.routing import Router
from flama.schemas.modules import SchemaModule

if typing.TYPE_CHECKING:
    from flama.components import Component
    from flama.modules import Module
    from flama.routing import BaseRoute, Mount

__all__ = ["Flama"]


DEFAULT_MODULES = [DatabaseModule, ResourcesModule, SchemaModule]


class Lifespan:
    def __init__(self, app: "Flama", lifespan: typing.Callable[["Flama"], typing.AsyncContextManager] = None):
        self.app = app
        self.lifespan = lifespan

    async def __aenter__(self):
        async with anyio.create_task_group() as tg:
            for module in self.app.modules.values():
                tg.start_soon(module.on_startup)

        if self.lifespan:  # pragma: no cover
            await self.lifespan.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.lifespan:  # pragma: no cover
            await self.lifespan.__aexit__(exc_type, exc_val, exc_tb)

        async with anyio.create_task_group() as tg:
            for module in self.app.modules.values():
                tg.start_soon(module.on_shutdown)

    def __call__(self, app: object) -> "Lifespan":
        return self


class Flama(Starlette):
    def __init__(
        self,
        routes: typing.Sequence[typing.Union["BaseRoute", "Mount"]] = None,
        components: typing.Optional[typing.List["Component"]] = None,
        modules: typing.Optional[typing.List["Module"]] = None,
        debug: bool = False,
        on_startup: typing.Sequence[typing.Callable] = None,
        on_shutdown: typing.Sequence[typing.Callable] = None,
        lifespan: typing.Callable[["Flama"], typing.AsyncContextManager] = None,
        database: typing.Optional[str] = None,
        title: typing.Optional[str] = "",
        version: typing.Optional[str] = "",
        description: typing.Optional[str] = "",
        schema: typing.Optional[str] = "/schema/",
        docs: typing.Optional[str] = "/docs/",
        redoc: typing.Optional[str] = None,
        *args,
        **kwargs
    ) -> None:
        super().__init__(debug=debug, *args, **kwargs)

        # Initialize components
        self.components = Components([*(components or [])])

        self.router = Router(
            main_app=self,
            routes=routes,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            lifespan=Lifespan(self, lifespan),
        )
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(self.router, debug=debug)
        self.error_middleware = ServerErrorMiddleware(self.exception_middleware, debug=debug)

        # Add exception handler for API exceptions
        self.add_exception_handler(HTTPException, self.api_http_exception_handler)

        # Initialize Modules
        self.modules = Modules(
            modules=[*DEFAULT_MODULES, *(modules or [])],
            app=self,
            *args,
            **{
                **{
                    "debug": debug,
                    "database": database,
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

    def __getattr__(self, item: str) -> "Module":
        return self.modules.__getattr__(item)

    @property
    def injector(self):
        return Injector(app=self)

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        self.components += getattr(app, "components", [])
        self.router.mount(path, app=app, name=name)

    def api_http_exception_handler(self, request: Request, exc: HTTPException) -> Response:
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
