import typing

from starlette.applications import Starlette as App
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.lifespan import LifespanMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from starlette_api import exceptions
from starlette_api.components import Component
from starlette_api.exceptions import HTTPException
from starlette_api.injector import Injector
from starlette_api.routing import Router
from starlette_api.schemas import SchemaMixin


class Starlette(App, SchemaMixin):
    def __init__(
        self,
        components: typing.Optional[typing.List[Component]] = None,
        debug: bool = False,
        title: str = "",
        version: str = "",
        description: str = "",
        schema: str = "/schema/",
        docs: str = "/docs/",
        redoc: str = None,
        *args,
        **kwargs
    ) -> None:
        super().__init__(debug=debug, *args, **kwargs)

        if components is None:
            components = []

        # Initialize injector
        self.components = components

        self.router = Router(components=components)
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(self.router, debug=debug)
        self.error_middleware = ServerErrorMiddleware(self.exception_middleware, debug=debug)
        self.lifespan_middleware = LifespanMiddleware(self.error_middleware)

        # Add exception handler for API exceptions
        self.add_exception_handler(exceptions.HTTPException, self.api_http_exception_handler)

        # Schema
        self.title = title
        self.version = version
        self.description = description
        self.schema_url = schema
        if self.schema_url:
            self.add_schema_route()

        # Docs (Swagger UI)
        self.docs_url = docs
        if self.docs_url:
            self.add_docs_route()

        # Redoc
        self.redoc_url = redoc
        if self.redoc_url:
            self.add_redoc_route()

    @property
    def injector(self):
        return Injector(components=self.components)

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        self.components += getattr(app, "components", [])
        self.router.mount(path, app=app, name=name)

    def api_http_exception_handler(self, request: Request, exc: HTTPException) -> Response:
        return JSONResponse(exc.detail, exc.status_code)
