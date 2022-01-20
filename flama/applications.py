import typing

from starlette.applications import Starlette
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.types import ASGIApp

from flama.components import Component
from flama.database import DatabaseModule
from flama.exceptions import HTTPException
from flama.http import Request, Response
from flama.injection import Injector
from flama.modules import Modules
from flama.resources import ResourcesModule
from flama.responses import APIErrorResponse
from flama.routing import Router
from flama.schemas.applications import AppDocsMixin, AppRedocMixin, AppSchemaMixin

if typing.TYPE_CHECKING:
    from flama.modules import Module

__all__ = ["Flama"]


DEFAULT_MODULES = [
    DatabaseModule,
    ResourcesModule,
]


class Flama(Starlette, AppSchemaMixin, AppDocsMixin, AppRedocMixin):
    def __init__(
        self,
        components: typing.Optional[typing.List[Component]] = None,
        modules: typing.Optional[typing.List["Module"]] = None,
        debug: bool = False,
        on_startup: typing.Sequence[typing.Callable] = None,
        on_shutdown: typing.Sequence[typing.Callable] = None,
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

        if components is None:
            components = []

        # Initialize injector
        self.components = components
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

        self.router = Router(components=self.components, on_startup=on_startup, on_shutdown=on_shutdown)
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(self.router, debug=debug)
        self.error_middleware = ServerErrorMiddleware(self.exception_middleware, debug=debug)

        # Add exception handler for API exceptions
        self.add_exception_handler(HTTPException, self.api_http_exception_handler)

        # Add schema and docs routes
        self.add_schema_routes(title=title, version=version, description=description, schema=schema)
        self.add_docs_route(docs=docs)
        self.add_redoc_route(redoc=redoc)

    def __getattr__(self, item: str) -> "Module":
        return self.modules.__getattr__(item)

    @property
    def injector(self):
        return Injector(components=self.components)

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        self.components += getattr(app, "components", [])
        self.router.mount(path, app=app, name=name)

    def add_component(self, component: Component):
        self.components.append(component)

    def api_http_exception_handler(self, request: Request, exc: HTTPException) -> Response:
        return APIErrorResponse(detail=exc.detail, status_code=exc.status_code, exception=exc)
