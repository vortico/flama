import typing

from starlette.applications import Starlette as App
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.types import ASGIApp

from starlette_api import exceptions
from starlette_api.components import Component
from starlette_api.exceptions import HTTPException
from starlette_api.http import Request, Response
from starlette_api.injection import Injector
from starlette_api.responses import APIErrorResponse
from starlette_api.routing import Router
from starlette_api.schemas import SchemaMixin

__all__ = ["Starlette"]


class Starlette(App, SchemaMixin):
    def __init__(
        self,
        components: typing.Optional[typing.List[Component]] = None,
        debug: bool = False,
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

        self.router = Router(components=components)
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(self.router, debug=debug)
        self.error_middleware = ServerErrorMiddleware(self.exception_middleware, debug=debug)

        # Add exception handler for API exceptions
        self.add_exception_handler(exceptions.HTTPException, self.api_http_exception_handler)

        # Add schema and docs routes
        self.add_schema_docs_routes(
            title=title, version=version, description=description, schema=schema, docs=docs, redoc=redoc
        )

    @property
    def injector(self):
        return Injector(components=self.components)

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        self.components += getattr(app, "components", [])
        self.router.mount(path, app=app, name=name)

    def api_http_exception_handler(self, request: Request, exc: HTTPException) -> Response:
        return APIErrorResponse(detail=exc.detail, status_code=exc.status_code, exception=exc)
