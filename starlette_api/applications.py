import asyncio
import inspect
import typing
from functools import wraps

from starlette.applications import Starlette as App
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Path
from starlette.types import ASGIApp, ASGIInstance, Receive, Scope, Send

from starlette_api import exceptions
from starlette_api.components import Component
from starlette_api.exceptions import HTTPException
from starlette_api.injector import Injector
from starlette_api.router import APIPath, get_route_from_scope
from starlette_api.schema import types


def asgi_from_http(func: typing.Callable, app: "Starlette") -> ASGIApp:
    """
    Wraps a http function into ASGI application.
    """
    @wraps(func)
    def _app(scope: Scope) -> ASGIInstance:
        async def awaitable(receive: Receive, send: Send) -> None:
            path, path_params = get_route_from_scope(app.router, scope)

            state = {
                'scope': scope,
                'receive': receive,
                'send': send,
                'exc': None,
                'app': None,
                'path_params': path_params,
                'api_path': path,
            }

            injected_func = await app.injector.inject(func, state)

            if asyncio.iscoroutinefunction(func):
                response = await injected_func()
            else:
                response = injected_func()

            if isinstance(response, (dict, list, types.Type)):
                response = JSONResponse(response)

            await response(receive, send)

        return awaitable

    return _app


def asgi_from_websocket(func: typing.Callable, app: "Starlette") -> ASGIApp:
    """
    Wraps websocket function into ASGI application.
    """
    @wraps(func)
    def _app(scope: Scope) -> ASGIInstance:
        async def awaitable(receive: Receive, send: Send) -> None:
            state = {
                'scope': scope,
                'receive': receive,
                'send': send,
                'exc': None,
                'app': app,
                'path_params': None,
                'route': get_route_from_scope(app.router, scope)
            }

            injected_func = await app.injector.inject(func, state)

            kwargs = scope.get("kwargs", {})
            await injected_func(**kwargs)

        return awaitable

    return _app


class Starlette(App):
    def __init__(self, components: typing.Optional[typing.List[Component]] = None, debug: bool = False) -> None:
        if components is None:
            components = []

        # Initialize injector
        self.injector = Injector(components)

        super().__init__(debug=debug)

        # Add exception handler for API exceptions
        self.add_exception_handler(exceptions.HTTPException, self.api_http_exception_handler)

    def route(self, path: str, method="GET"):
        def decorator(func):
            self.add_route(path, func, method)
            return func

        return decorator

    def add_route(self, path: str, route: typing.Callable, method: str="GET") -> None:
        if not inspect.isclass(route):
            route = asgi_from_http(route, self)
        else:
            route.injector = self.injector
            route.app = self

        instance = APIPath(path, route, protocol="http", method=method)
        self.router.routes.append(instance)

    def add_websocket_route(self, path: str, route: typing.Callable) -> None:
        if not inspect.isclass(route):
            route = asgi_from_websocket(route, self)
        else:
            route.injector = self.injector
            route.app = self

        instance = Path(path, route, protocol="websocket")
        self.router.routes.append(instance)

    def api_http_exception_handler(self, request: Request, exc: HTTPException) -> Response:
        return JSONResponse(exc.detail, exc.status_code)