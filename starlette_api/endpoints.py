import asyncio
import typing

from starlette.endpoints import HTTPEndpoint as BaseHTTPEndpoint
from starlette.requests import Request
from starlette.responses import Response

from starlette_api.injector import Injector


class HTTPEndpoint(BaseHTTPEndpoint):
    def __init__(self, *args: typing.Any, injector: Injector = None, **kwargs: typing.Any):
        super().__init__(*args, **kwargs)
        self._injector = injector

    @property
    def injector(self) -> Injector:
        if self._injector is None:
            raise AttributeError("Injector is not initialized")

        return self._injector

    @injector.setter
    def injector(self, injector: Injector):
        self._injector = injector

    async def dispatch(self, request: Request, **kwargs: typing.Any) -> Response:
        handler_name = "get" if request.method == "HEAD" else request.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        injected_func = await self.injector.inject(handler)

        if asyncio.iscoroutinefunction(handler):
            response = await injected_func(request=request)
        else:
            response = injected_func(request=request)
        return response
