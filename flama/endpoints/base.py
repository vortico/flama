import typing as t

from flama import types
from flama.context import Context

__all__ = ["BaseEndpoint"]


class BaseEndpoint(types.EndpointProtocol):
    state: Context

    def __init__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        """An endpoint.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        """
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
        )

    def __await__(self) -> t.Generator:
        return self.dispatch().__await__()
