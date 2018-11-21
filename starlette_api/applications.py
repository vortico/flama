import typing

from starlette.applications import Starlette as App
from starlette.exceptions import ExceptionMiddleware
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

        # Add exception handler for API exceptions
        self.add_exception_handler(exceptions.HTTPException, self.api_http_exception_handler)

    def route(self, path: str, methods: typing.List[str] = None) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_route(path, func, methods=methods)
            return func

        return decorator

    def websocket_route(self, path: str) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_websocket_route(path, func)
            return func

        return decorator

    def add_route(self, path: str, endpoint: typing.Callable, methods: typing.Sequence[str] = None) -> None:
        self.router.add_route(path, endpoint=endpoint, methods=methods)

    def add_websocket_route(self, path: str, endpoint: typing.Callable) -> None:
        self.router.add_websocket_route(path, endpoint)

    def api_http_exception_handler(self, request: Request, exc: HTTPException) -> Response:
        return JSONResponse(exc.detail, exc.status_code)
