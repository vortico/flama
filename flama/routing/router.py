import logging
import typing as t

from flama import exceptions, types, url
from flama._core.route_table import RouteTable
from flama.injection import Component, Components
from flama.lifespan import Lifespan
from flama.routing.routes.base import BaseRoute, ResolveResult, ResolveType, ScopeType
from flama.routing.routes.http import Route
from flama.routing.routes.mount import Mount
from flama.routing.routes.websocket import WebSocketRoute

__all__ = ["Router"]

logger = logging.getLogger(__name__)


def _parse_resolve_result(raw: t.Any) -> ResolveResult | None:
    if raw is None:
        return None
    if raw[0] == 2:
        return ResolveResult(type=ResolveType.method_not_allowed, index=raw[1], allowed_methods=list(raw[2]))
    return ResolveResult(
        type=ResolveType.mount if raw[0] == 1 else ResolveType.full,
        index=raw[1],
        params=tuple(raw[2]),
        matched=raw[3],
        unmatched=raw[4],
    )


class Router:
    def __init__(
        self,
        routes: t.Sequence[BaseRoute] | None = None,
        *,
        app: types.App,
        components: t.Sequence["Component"] | set["Component"] | None = None,
        lifespan: t.Callable[[types.App | None], t.AsyncContextManager] | None = None,
    ):
        """A router for containing all routes and mount points.

        :param routes: Routes part of this router.
        :param components: Components registered in this router.
        :param lifespan: Lifespan function.
        :param root: Flama application.
        """
        self.app = app
        self.routes: list[BaseRoute] = [] if routes is None else list(routes)
        self.components = Components(components if components else set())
        self.lifespan = Lifespan(lifespan)
        self._route_table = RouteTable()

        for route in self.routes:
            route._build(self.app)
            self._register_route_entry(route)

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

    def _register_route_entry(self, route: BaseRoute) -> None:
        try:
            params = route._route_table_params
            self._route_table.add_entry(
                route.path._matcher, params.scope_type, params.accept_partial_path, params.methods
            )
        except (AttributeError, TypeError, ValueError):
            pass

    def add_component(self, component: Component):
        """Register a new component.

        :param component: Component to register.
        """
        self.components = Components(self.components + (component,))

    def add_route(
        self,
        path: str | None = None,
        endpoint: types.HTTPHandler | None = None,
        methods: list[str] | None = None,
        *,
        name: str | None = None,
        include_in_schema: bool = True,
        route: Route | None = None,
        pagination: types.Pagination | None = None,
        tags: dict[str, t.Any] | None = None,
    ) -> Route:
        """Register a new HTTP route in this router under given path.

        :param path: URL path.
        :param endpoint: HTTP endpoint.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param route: HTTP route.
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
            raise exceptions.ApplicationError("Either 'path' and 'endpoint', or 'route' variables are needed")

        self.routes.append(route)
        route._build(self.app)
        self._register_route_entry(route)
        return route

    def route(
        self,
        path: str,
        methods: list[str] | None = None,
        *,
        name: str | None = None,
        include_in_schema: bool = True,
        pagination: types.Pagination | None = None,
        tags: dict[str, t.Any] | None = None,
    ) -> t.Callable[[types.HTTPHandler], types.HTTPHandler]:
        """Decorator version for registering a new HTTP route in this router under given path.

        :param path: URL path.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
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
                pagination=pagination,
                tags=tags,
            )
            return func

        return decorator

    def add_websocket_route(
        self,
        path: str | None = None,
        endpoint: types.WebSocketHandler | None = None,
        *,
        name: str | None = None,
        route: WebSocketRoute | None = None,
        pagination: types.Pagination | None = None,
        tags: dict[str, t.Any] | None = None,
    ) -> WebSocketRoute:
        """Register a new websocket route in this router under given path.

        :param path: URL path.
        :param endpoint: Websocket function or endpoint.
        :param name: Websocket route name.
        :param route: Specific route class.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the websocket route.
        :return: Websocket route.
        """
        if path is not None and endpoint is not None:
            route = WebSocketRoute(path, endpoint=endpoint, name=name, pagination=pagination, tags=tags)

        if route is None:
            raise exceptions.ApplicationError("Either 'path' and 'endpoint', or 'route' variables are needed")

        self.routes.append(route)
        route._build(self.app)
        self._register_route_entry(route)
        return route

    def websocket_route(
        self,
        path: str,
        *,
        name: str | None = None,
        pagination: types.Pagination | None = None,
        tags: dict[str, t.Any] | None = None,
    ) -> t.Callable[[types.WebSocketHandler], types.WebSocketHandler]:
        """Decorator version for registering a new websocket route in this router under given path.

        :param path: URL path.
        :param name: Websocket route name.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the websocket route.
        :return: Decorated websocket route.
        """

        def decorator(func: types.WebSocketHandler) -> types.WebSocketHandler:
            self.add_websocket_route(path, func, name=name, pagination=pagination, tags=tags)
            return func

        return decorator

    def mount(
        self,
        path: str | None = None,
        app: types.App | None = None,
        *,
        name: str | None = None,
        mount: Mount | None = None,
        tags: dict[str, t.Any] | None = None,
    ) -> Mount:
        """Register a new mount point containing an ASGI app in this router under given path.

        :param path: URL path.
        :param app: ASGI app to mount.
        :param name: Route name.
        :param mount: Mount.
        :param tags: Tags to add to the mount.
        :return: Mount.
        """
        if path is not None and app is not None:
            mount = Mount(path, app=app, name=name, tags=tags)

        if mount is None:
            raise exceptions.ApplicationError("Either 'path' and 'app', or 'mount' variables are needed")

        self.routes.append(mount)
        mount._build(self.app)
        self._register_route_entry(mount)
        return mount

    def resolve_route(self, scope: types.Scope) -> tuple[BaseRoute, types.Scope]:
        """Look for a route that matches given ASGI scope.

        :param scope: ASGI scope.
        :raise MethodNotAllowedException: If route is resolved but http method is not valid.
        :raise NotFoundException: If route cannot be resolved.
        :return: Route and its scope.
        """
        scope_type = ScopeType.__members__.get(scope["type"], ScopeType(0))
        result = _parse_resolve_result(self._route_table.resolve(scope["path"], scope_type, scope.get("method", "")))

        if result is None:
            raise exceptions.NotFoundException(
                path=scope.get("root_path", "") + scope["path"], params=scope.get("path_params")
            )

        route = self.routes[result.index]

        if result.type == ResolveType.method_not_allowed:
            route_scope = types.Scope({**scope, **route.route_scope(scope)})
            raise exceptions.MethodNotAllowedException(
                route_scope.get("root_path", "") + route_scope["path"],
                route_scope["method"],
                set(result.allowed_methods or []),
            )

        if result.type == ResolveType.mount:
            is_flama = types.is_flama_instance(route.app)
            mount_scope = {"app": route.app if is_flama else scope["app"]}
            if "path" in scope:
                mount_scope["root_path"] = (
                    "" if is_flama else str(url.Path(scope.get("root_path", "")) / (result.matched or ""))
                )
                mount_scope["path"] = str(url.Path("/") / (result.unmatched or ""))
            route_scope = types.Scope({**scope, **mount_scope})
            try:
                return route.app.resolve_route(route_scope)
            except AttributeError:
                return route, route_scope

        route_scope = types.Scope({**scope, **route.route_scope(scope)})
        return route, route_scope

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
