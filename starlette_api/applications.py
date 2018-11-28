import typing

from starlette.applications import Starlette as App
from starlette.exceptions import ExceptionMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.lifespan import LifespanMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from starlette_api import exceptions
from starlette_api.components import Component
from starlette_api.exceptions import HTTPException
from starlette_api.injector import Injector
from starlette_api.routing import Router


class Starlette(App):
    def __init__(
        self, components: typing.Optional[typing.List[Component]] = None, debug: bool = False, *args, **kwargs
    ) -> None:
        super().__init__(debug=debug, *args, **kwargs)

        if components is None:
            components = []

        # Initialize injector
        self.injector = Injector(components)

        self.router = Router()
        self.app = self.router
        self.exception_middleware = ExceptionMiddleware(self.router, debug=debug)
        self.error_middleware = ServerErrorMiddleware(self.exception_middleware, debug=debug)
        self.lifespan_middleware = LifespanMiddleware(self.error_middleware)

        # Add exception handler for API exceptions
        self.add_exception_handler(exceptions.HTTPException, self.api_http_exception_handler)

    def api_http_exception_handler(self, request: Request, exc: HTTPException) -> Response:
        return JSONResponse(exc.detail, exc.status_code)
