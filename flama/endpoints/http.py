import typing as t

from flama import concurrency, http, types
from flama.context import Context
from flama.endpoints.base import BaseEndpoint
from flama.types.http import ALL_METHODS, Method

__all__ = ["HTTPEndpoint"]


class HTTPEndpoint(BaseEndpoint, types.HTTPEndpointProtocol):
    scope_type = "http"
    state: Context

    def build_context(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> dict[str, t.Any]:
        """Build the HTTP-specific context fields.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        :return: Mapping with the request bound to this endpoint.
        """
        return {"request": http.Request(scope, receive=receive)}

    @classmethod
    def allowed_methods(cls) -> set[Method]:
        """The list of allowed methods by this endpoint.

        :return: List of allowed methods.
        """
        methods = {m for m in ALL_METHODS if getattr(cls, m.lower(), None) is not None}
        if "GET" in methods:
            methods.add("HEAD")
        return methods

    @classmethod
    def allowed_handlers(cls) -> dict[str, t.Callable[..., t.Awaitable[t.Any] | t.Any]]:
        """A mapping of handler related to each HTTP method.

        :return: Handlers mapping.
        """
        return {method: getattr(cls, method.lower(), getattr(cls, "get")) for method in cls.allowed_methods()}

    async def resolve_handler(self) -> t.Callable[..., t.Awaitable[t.Any] | t.Any]:
        """Resolve the handler used for dispatching this request.

        :return: Handler.
        """
        request = self.state.request
        handler_name = "get" if request.method == "HEAD" else request.method.lower()
        return getattr(self, handler_name)

    async def dispatch(self) -> t.Any:
        """Dispatch a request."""
        handler = await self.state.app.injector.inject(await self.resolve_handler(), self.state)
        return await concurrency.run(handler)
