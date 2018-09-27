import asyncio

from starlette.endpoints import HTTPEndpoint as BaseHTTPEndpoint
from starlette.requests import Request

from starlette_api.injector import Injector


class HTTPEndpoint(BaseHTTPEndpoint):
    def __init__(self, *args, injector: Injector = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._injector = injector

    @property
    def injector(self):
        if self._injector is None:
            raise AttributeError("Injector is not initialized")

        return self._injector

    @injector.setter
    def injector(self, injector):
        self._injector = injector

    async def dispatch(self, request: Request, **kwargs):
        handler_name = "get" if request.method == "HEAD" else request.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        injected_func = await self.injector.inject(handler)

        if asyncio.iscoroutinefunction(handler):
            response = await injected_func(request=request)
        else:
            response = injected_func(request=request)
        return response
