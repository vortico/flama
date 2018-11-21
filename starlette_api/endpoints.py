import asyncio
import inspect
import typing

from starlette.endpoints import HTTPEndpoint as BaseHTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Send

import marshmallow


class HTTPEndpoint(BaseHTTPEndpoint):
    async def __call__(self, receive: Receive, send: Send):
        request = Request(self.scope, receive=receive)
        app = self.scope["app"]
        kwargs = self.scope.get("kwargs", {})

        route, route_scope = app.router.get_route_from_scope(self.scope)

        state = {
            "scope": self.scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "path_params": route_scope["path_params"],
            "route": route,
        }
        response = await self.dispatch(request, state, **kwargs)

        return await response(receive, send)

    async def dispatch(self, request: Request, state: typing.Dict, **kwargs) -> Response:
        handler_name = "get" if request.method == "HEAD" else request.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        app = state["app"]
        injected_func = await app.injector.inject(handler, state)

        if asyncio.iscoroutinefunction(handler):
            response = await injected_func()
        else:
            response = injected_func()

        return_annotation = inspect.signature(handler).return_annotation
        if issubclass(return_annotation, marshmallow.Schema):
            response = return_annotation().dump(response)

        if isinstance(response, (dict, list)):
            response = JSONResponse(response)
        elif isinstance(response, str):
            response = Response(response)

        return response
