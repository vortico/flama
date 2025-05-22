import inspect
import logging
import typing as t

from flama import compat, endpoints, exceptions, types, websockets
from flama.routing.routes.base import BaseEndpointWrapper, BaseRoute

if t.TYPE_CHECKING:
    from flama import Flama

__all__ = ["WebSocketRoute"]

logger = logging.getLogger(__name__)


class WebSocketFunctionWrapper(BaseEndpointWrapper):
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        app: Flama = scope["app"]
        scope["path"] = scope.get("root_path", "").rstrip("/") + scope["path"]
        scope["root_path"] = ""
        route, route_scope = app.router.resolve_route(scope)
        context = {
            "scope": route_scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "route": route,
            "websocket": websockets.WebSocket(route_scope, receive, send),
            "websocket_encoding": None,
            "websocket_code": None,
            "websocket_message": None,
        }

        injected_func = await app.injector.inject(self.handler, context)
        await injected_func(**route_scope.get("kwargs", {}))


class WebSocketEndpointWrapper(BaseEndpointWrapper):
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        await self.handler(scope, receive, send)


class WebSocketRoute(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: types.WebSocketHandler,
        *,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        pagination: t.Optional[types.Pagination] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ):
        """A route definition of a websocket endpoint.

        :param path: URL path.
        :param endpoint: Websocket endpoint or function.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param pagination: Apply a pagination technique.
        :param tags: Route tags.
        """

        if not (self.is_endpoint(endpoint) or (not inspect.isclass(endpoint) and callable(endpoint))):
            raise exceptions.ApplicationError("Endpoint must be a callable or a WebSocketEndpoint subclass")

        name = endpoint.__name__ if name is None else name
        wrapper = WebSocketEndpointWrapper if inspect.isclass(endpoint) else WebSocketFunctionWrapper

        super().__init__(
            path, wrapper(endpoint, pagination=pagination), name=name, include_in_schema=include_in_schema, tags=tags
        )

        self.app: BaseEndpointWrapper

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] == "websocket":
            await self.handle(types.Scope({**scope, **self.route_scope(scope)}), receive, send)

    @staticmethod
    def is_endpoint(
        x: types.WebSocketHandler,
    ) -> compat.TypeGuard[type[endpoints.WebSocketEndpoint]]:  # PORT: Replace compat when stop supporting 3.9
        return inspect.isclass(x) and issubclass(x, endpoints.WebSocketEndpoint)

    def endpoint_handlers(self) -> dict[str, t.Callable]:
        """Return a mapping of all possible endpoints of this route.

        Useful to identify all endpoints by HTTP methods.

        :return: Mapping of all endpoints.
        """
        if self.is_endpoint(self.endpoint):
            return self.endpoint.allowed_handlers()

        return {"WEBSOCKET": self.endpoint}

    def match(self, scope: types.Scope) -> BaseRoute.Match:
        """Check if this route matches with given scope.

        :param scope: ASGI scope.
        :return: Match.
        """
        if scope["type"] != "websocket":
            return self.Match.none

        return super().match(scope)
