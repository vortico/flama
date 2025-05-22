import logging
import typing as t

from flama import exceptions, types, url
from flama.injection import Component, Components
from flama.lifespan import Lifespan
from flama.routing.routes.base import BaseRoute
from flama.routing.routes.http import Route
from flama.routing.routes.mount import Mount
from flama.routing.routes.websocket import WebSocketRoute

if t.TYPE_CHECKING:
    from flama.applications import Flama, types


__all__ = ["Router"]

logger = logging.getLogger(__name__)


class Router:
    def __init__(
        self,
        routes: t.Optional[t.Sequence[BaseRoute]] = None,
        *,
        components: t.Optional[t.Union[t.Sequence["Component"], set["Component"]]] = None,
        lifespan: t.Optional[t.Callable[[t.Optional["Flama"]], t.AsyncContextManager]] = None,
        root: t.Optional["Flama"] = None,
    ):
        """A router for containing all routes and mount points.

        :param routes: Routes part of this router.
        :param components: Components registered in this router.
        :param lifespan: Lifespan function.
        :param root: Flama application.
        """
        self.routes = [] if routes is None else list(routes)
        self.components = Components(components if components else set())
        self.lifespan = Lifespan(lifespan)

        if root:
            self.build(root)

    def __hash__(self) -> int:
        return hash(tuple(self.routes))

    def __eq__(self, other: t.Any) -> bool:
        return isinstance(other, Router) and self.routes == other.routes

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        logger.debug("Request: %s", str(scope))
        if scope["type"] not in ("http", "websocket", "lifespan"):
            raise ValueError(f"Wrong scope type ({scope['type']})")

        if scope["type"] == "lifespan":
            await self.lifespan(scope, receive, send)
            return

        if "router" not in scope:
            scope["router"] = self

        route, route_scope = self.resolve_route(scope)
        await route(route_scope, receive, send)

    def build(self, app: "Flama") -> None:
        """Build step for routes.

        Just build the parameters' descriptor part of RouteParametersMixin.

        :param app: Flama app.
        """
        for route in self.routes:
            route.build(app)

    def add_component(self, component: Component):
        """Register a new component.

        :param component: Component to register.
        """
        self.components = Components(self.components + Components([component]))

    def add_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.HTTPHandler] = None,
        methods: t.Optional[list[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        *,
        route: t.Optional[Route] = None,
        root: t.Optional["Flama"] = None,
        pagination: t.Optional[types.Pagination] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> Route:
        """Register a new HTTP route in this router under given path.

        :param path: URL path.
        :param endpoint: HTTP endpoint.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param route: HTTP route.
        :param root: Flama application.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the route or endpoint.
        :return: Route.
        """
        if path is not None and endpoint is not None:
            route = Route(
                path,
                endpoint=endpoint,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
                pagination=pagination,
                tags=tags,
            )

        if route is None:
            raise exceptions.ApplicationError("Either 'path' and 'endpoint' or 'route' variables are needed")

        self.routes.append(route)

        route.build(root)

        return route

    def route(
        self,
        path: str,
        methods: t.Optional[list[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        *,
        root: t.Optional["Flama"] = None,
        pagination: t.Optional[types.Pagination] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> t.Callable[[types.HTTPHandler], types.HTTPHandler]:
        """Decorator version for registering a new HTTP route in this router under given path.

        :param path: URL path.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param root: Flama application.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the endpoint.
        :return: Decorated route.
        """

        def decorator(func: types.HTTPHandler) -> types.HTTPHandler:
            self.add_route(
                path,
                func,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
                root=root,
                pagination=pagination,
                tags=tags,
            )
            return func

        return decorator

    def add_websocket_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.WebSocketHandler] = None,
        name: t.Optional[str] = None,
        *,
        route: t.Optional[WebSocketRoute] = None,
        root: t.Optional["Flama"] = None,
        pagination: t.Optional[types.Pagination] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> WebSocketRoute:
        """Register a new websocket route in this router under given path.

        :param path: URL path.
        :param endpoint: Websocket function or endpoint.
        :param name: Websocket route name.
        :param route: Specific route class.
        :param root: Flama application.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the websocket route.
        :return: Websocket route.
        """
        if path is not None and endpoint is not None:
            route = WebSocketRoute(path, endpoint=endpoint, name=name, pagination=pagination, tags=tags)

        if route is None:
            raise exceptions.ApplicationError("Either 'path' and 'endpoint' or 'route' variables are needed")

        self.routes.append(route)

        route.build(root)

        return route

    def websocket_route(
        self,
        path: str,
        name: t.Optional[str] = None,
        *,
        root: t.Optional["Flama"] = None,
        pagination: t.Optional[types.Pagination] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> t.Callable[[types.WebSocketHandler], types.WebSocketHandler]:
        """Decorator version for registering a new websocket route in this router under given path.

        :param path: URL path.
        :param name: Websocket route name.
        :param root: Flama application.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the websocket route.
        :return: Decorated websocket route.
        """

        def decorator(func: types.WebSocketHandler) -> types.WebSocketHandler:
            self.add_websocket_route(path, func, name=name, root=root, pagination=pagination, tags=tags)
            return func

        return decorator

    def mount(
        self,
        path: t.Optional[str] = None,
        app: t.Optional[types.App] = None,
        name: t.Optional[str] = None,
        *,
        mount: t.Optional[Mount] = None,
        root: t.Optional["Flama"] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> Mount:
        """Register a new mount point containing an ASGI app in this router under given path.

        :param path: URL path.
        :param app: ASGI app to mount.
        :param name: Route name.
        :param mount: Mount.
        :param root: Flama application.
        :param tags: Tags to add to the mount.
        :return: Mount.
        """
        if path is not None and app is not None:
            mount = Mount(path, app=app, name=name, tags=tags)

        if mount is None:
            raise exceptions.ApplicationError("Either 'path' and 'app' or 'mount' variables are needed")

        self.routes.append(mount)

        mount.build(root)

        return mount

    def resolve_route(self, scope: types.Scope) -> tuple[BaseRoute, types.Scope]:
        """Look for a route that matches given ASGI scope.

        :param scope: ASGI scope.
        :raise MethodNotAllowedException: If route is resolved but http method is not valid.
        :raise NotFoundException: If route cannot be resolved.
        :return: Route and its scope.
        """
        partial = None
        partial_allowed_methods: set[str] = set()

        for route in self.routes:
            m = route.match(scope)
            if m == route.Match.full:
                route_scope = types.Scope({**scope, **route.route_scope(scope)})

                if isinstance(route, Mount):
                    try:
                        return route.app.resolve_route(route_scope)  # type: ignore[no-any-return,union-attr]
                    except AttributeError:
                        ...

                return route, route_scope
            elif m == route.Match.partial:
                partial = route
                if isinstance(route, Route):
                    partial_allowed_methods |= route.methods

        if partial:
            route_scope = types.Scope({**scope, **partial.route_scope(scope)})
            raise exceptions.MethodNotAllowedException(
                route_scope.get("root_path", "") + route_scope["path"], route_scope["method"], partial_allowed_methods
            )

        raise exceptions.NotFoundException(
            path=scope.get("root_path", "") + scope["path"], params=scope.get("path_params")
        )

    def resolve_url(self, name: str, **path_params: t.Any) -> url.URL:
        """Look for a route URL given the route name and path params.

        :param name: Route name.
        :param path_params: Path params.
        :return: Route URL.
        """
        for route in self.routes:
            try:
                return route.resolve_url(name, **path_params)
            except exceptions.NotFoundException:
                pass
        raise exceptions.NotFoundException(params=path_params, name=name)
