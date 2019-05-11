import os
import typing

from starlette.applications import Starlette
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.types import ASGIApp

from flama import exceptions
from flama.components import Component
from flama.exceptions import HTTPException
from flama.injection import Injector
from flama.responses import APIErrorResponse
from flama.routing import Router
from flama.types.http import Request, Response

if typing.TYPE_CHECKING:
    from flama.resources import BaseResource

__all__ = ["BaseApp"]


class BaseApp(Starlette):
    TEMPLATES_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "templates"))

    def __init__(self, components: typing.Optional[typing.List[Component]] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if components is None:
            components = []

        # Initialize injector
        self.components = components

        self.router = Router(components=components)
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(self.router, debug=self._debug)
        self.error_middleware = ServerErrorMiddleware(self.exception_middleware, debug=self._debug)

        # Add exception handler for API exceptions
        self.add_exception_handler(exceptions.HTTPException, self.api_http_exception_handler)

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
