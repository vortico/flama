import asyncio
import inspect
import typing

from starlette.applications import Starlette as App
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Path
from starlette.types import ASGIApp, ASGIInstance, Receive, Scope, Send
from starlette.websockets import WebSocket

from starlette_api.components import Component
from starlette_api.injector import Injector


def asgi_from_http(func: typing.Callable, injector: Injector) -> ASGIApp:
    """
    Wraps a http function into ASGI application.
    """

    def app(scope: Scope) -> ASGIInstance:
        async def awaitable(receive: Receive, send: Send) -> None:
            request = Request(scope, receive=receive)

            injected_func = await injector.inject(func)

            if asyncio.iscoroutinefunction(func):
                response = await injected_func(request=request)
            else:
                response = injected_func(request=request)

            if isinstance(response, (dict, list)):
                response = JSONResponse(response)

            await response(receive, send)

        return awaitable

    return app


def asgi_from_websocket(func: typing.Callable, injector: Injector) -> ASGIApp:
    """
    Wraps websocket function into ASGI application.
    """

    def app(scope: Scope) -> ASGIInstance:
        async def awaitable(receive: Receive, send: Send) -> None:
            session = WebSocket(scope, receive=receive, send=send)
            kwargs = scope.get("kwargs", {})

            injected_func = await injector.inject(func)

            await injected_func(session, **kwargs)

        return awaitable

    return app


class Starlette(App):
    def __init__(self, components: typing.Optional[typing.List[Component]] = None, debug: bool = False) -> None:
        if components is None:
            components = []

        self.injector = Injector(components)

        super().__init__(debug=debug)

    def add_route(self, path: str, route: typing.Callable, methods: typing.Sequence[str]=()) -> None:
        if not inspect.isclass(route):
            route = asgi_from_http(route, self.injector)
            if not methods:
                methods = ("GET",)
        else:
            route.injector = self.injector

        instance = Path(path, route, protocol="http", methods=methods)
        self.router.routes.append(instance)

    def add_websocket_route(self, path: str, route: typing.Callable) -> None:
        if not inspect.isclass(route):
            route = asgi_from_websocket(route, self.injector)
        else:
            route.injector = self.injector

        instance = Path(path, route, protocol="websocket")
        self.router.routes.append(instance)
