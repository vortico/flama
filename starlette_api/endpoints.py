import asyncio
import typing

from starlette.endpoints import HTTPEndpoint as BaseHTTPEndpoint
from starlette.requests import Request
from starlette.types import Receive, Send

from starlette_api.applications import Starlette
from starlette_api.injector import Injector
from starlette_api.router import get_route_from_scope


class HTTPEndpoint(BaseHTTPEndpoint):
    def __init__(self, *args, app: Starlette = None, injector: Injector = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._app = app
        self._injector = injector

    @property
    def injector(self):
        if self._injector is None:
            raise AttributeError("Injector is not initialized")

        return self._injector

    @injector.setter
    def injector(self, injector):
        self._injector = injector

    @property
    def app(self):
        if self._app is None:
            raise AttributeError("App is not initialized")

        return self._app

    @app.setter
    def app(self, app):
        self._app = app

    async def __call__(self, receive: Receive, send: Send) -> None:
        request = Request(self.scope, receive=receive)
        kwargs = self.scope.get("kwargs", {})

        api_path, path_params = get_route_from_scope(self.app.router, self.scope)

        state = {
            "scope": self.scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": self.app,
            "path_params": path_params,
            "api_path": api_path,
        }
        response = await self.dispatch(request, state, **kwargs)
        await response(receive, send)

    async def dispatch(self, request: Request, state: typing.Mapping, **kwargs):
        handler_name = "get" if request.method == "HEAD" else request.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        injected_func = await self.injector.inject(handler, state)

        if asyncio.iscoroutinefunction(handler):
            response = await injected_func()
        else:
            response = injected_func()
        return response
