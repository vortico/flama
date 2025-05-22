import typing as t

from flama import types

if t.TYPE_CHECKING:
    from flama import Flama

__all__ = ["BaseEndpoint"]


class BaseEndpoint(types.EndpointProtocol):
    def __init__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        """An endpoint.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        """
        app: Flama = scope["app"]
        scope["path"] = scope.get("root_path", "").rstrip("/") + scope["path"]
        scope["root_path"] = ""
        route, route_scope = app.router.resolve_route(scope)
        self.state = {
            "scope": route_scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "route": route,
        }

    def __await__(self) -> t.Generator:
        return self.dispatch().__await__()
