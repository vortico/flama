import typing

import marshmallow
from starlette.applications import Starlette
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.types import ASGIApp

from flama import exceptions
from flama.components import Component
from flama.exceptions import HTTPException
from flama.http import Request, Response
from flama.injection import Injector
from flama.responses import APIErrorResponse
from flama.routing import Router
from flama.schemas import SchemaMixin

if typing.TYPE_CHECKING:
    from flama.resources import BaseResource

__all__ = ["Flama"]


class Flama(Starlette, SchemaMixin):
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
        on_startup: typing.Sequence[typing.Callable] = None,
        on_shutdown: typing.Sequence[typing.Callable] = None,
        *args,
        **kwargs
    ) -> None:
        super().__init__(debug=debug, *args, **kwargs)

        if components is None:
            components = []

        # Initialize injector
        self.components = components

        self.router = Router(components=components, on_startup=on_startup, on_shutdown=on_shutdown)
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

    def add_resource(self, path: str, resource: "BaseResource"):
        self.router.add_resource(path, resource=resource)

    def resource(self, path: str) -> typing.Callable:
        def decorator(resource: "BaseResource") -> "BaseResource":
            self.router.add_resource(path, resource=resource)
            return resource

        return decorator

    def api_http_exception_handler(self, request: Request, exc: HTTPException) -> Response:
        return APIErrorResponse(detail=exc.detail, status_code=exc.status_code, exception=exc)

    def schemas(
        self,
        response_schema: marshmallow.Schema = None,
        **request_schemas: typing.Dict[str, marshmallow.Schema]
    ):
        def decorator(func):
            func._request_schemas = request_schemas
            func._response_schema = response_schema
            return func

        return decorator

    def route(
        self,
        path: str,
        methods: typing.List[str] = None,
        name: str = None,
        include_in_schema: bool = True,
        response_schema: marshmallow.Schema = None,
        **request_schemas: typing.Dict[str, marshmallow.Schema]
    ) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.router.add_route(
                path,
                func,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
                response_schema=response_schema,
                request_schemas=request_schemas,
            )
            return func

        return decorator
