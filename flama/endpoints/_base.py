import abc
import typing as t

from flama import types
from flama.context import Context

__all__ = ["BaseEndpoint"]


class BaseEndpoint(types.EndpointProtocol):
    scope_type: t.ClassVar[str]
    state: Context

    def __init__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        """An endpoint.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        """
        if scope["type"] != self.scope_type:
            raise ValueError("Wrong scope")

        app: types.App = scope["app"]
        scope["path"] = scope.get("root_path", "").rstrip("/") + scope["path"]
        scope["root_path"] = ""
        route, route_scope = app.router.resolve_route(scope)
        self.state = Context(
            scope=route_scope,
            receive=receive,
            send=send,
            app=app,
            route=route,
            **self.build_context(scope, receive, send),
        )

    @abc.abstractmethod
    def build_context(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> dict[str, t.Any]:
        """Build the endpoint-specific context fields added on top of the shared ones.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        :return: Mapping of extra context fields.
        """
        ...

    def __await__(self) -> t.Generator:
        return self.dispatch().__await__()
