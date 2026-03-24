import typing as t

from flama import concurrency, http, types
from flama.context import Context
from flama.endpoints.base import BaseEndpoint
from flama.types.http import ALL_METHODS, Method

__all__ = ["HTTPEndpoint"]


class HTTPEndpoint(BaseEndpoint, types.HTTPEndpointProtocol):
    state: Context

    def __init__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        """An HTTP endpoint.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        """
        if scope["type"] != "http":
            raise ValueError("Wrong scope")

        super().__init__(scope, receive, send)

        self.state = Context(
            scope=self.state.scope,
            receive=self.state.receive,
            send=self.state.send,
            app=self.state.app,
            route=self.state.route,
            request=http.Request(scope, receive=receive),
        )

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
    def allowed_handlers(cls) -> dict[str, t.Callable]:
        """A mapping of handler related to each HTTP method.

        :return: Handlers mapping.
        """
        return {method: getattr(cls, method.lower(), getattr(cls, "get")) for method in cls.allowed_methods()}

    @property
    def handler(self) -> t.Callable:
        """The handler used for dispatching this request.

        :return: Handler.
        """
        assert self.state.request is not None
        handler_name = "get" if self.state.request.method == "HEAD" else self.state.request.method.lower()
        h: t.Callable = getattr(self, handler_name)
        return h

    async def dispatch(self) -> t.Any:
        """Dispatch a request."""
        assert self.state.app is not None
        handler = await self.state.app.injector.inject(self.handler, self.state)
        return await concurrency.run(handler)
