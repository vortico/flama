import abc
import builtins
import enum
import functools
import inspect
import logging
import typing as t

from flama import compat, concurrency, endpoints, exceptions, http, schemas, types, url, websockets
from flama.injection import Component, Components
from flama.lifespan import Lifespan
from flama.pagination import paginator
from flama.schemas.routing import RouteParametersMixin

if t.TYPE_CHECKING:
    from flama.applications import Flama
    from flama.pagination.types import PaginationType

__all__ = ["Route", "WebSocketRoute", "Mount", "Router"]

logger = logging.getLogger(__name__)


class _EndpointType(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
    http = enum.auto()
    websocket = enum.auto()


class Match(enum.Enum):
    none = enum.auto()
    partial = enum.auto()
    full = enum.auto()


class EndpointWrapper:
    type = _EndpointType

    def __init__(
        self,
        handler: t.Union[t.Callable, builtins.type[endpoints.HTTPEndpoint], builtins.type[endpoints.WebSocketEndpoint]],
        endpoint_type: _EndpointType,
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
    ):
        """Wraps a function or endpoint into ASGI application.

        :param handler: Function or endpoint.
        :param endpoint_type: Endpoint type, http or websocket.
        :param pagination: Apply a pagination technique.
        """
        if pagination:
            handler = paginator.paginate(pagination, handler)

        self.handler = handler
        functools.update_wrapper(self, handler)
        decorator_select: dict[tuple[_EndpointType, bool], types.App] = {
            (self.type.http, False): self._http_function,
            (self.type.http, True): self._http_endpoint,
            (self.type.websocket, False): self._websocket_function,
            (self.type.websocket, True): self._websocket_endpoint,
        }
        self.call_function = decorator_select[(endpoint_type, inspect.isclass(self.handler))]

    def __get__(self, instance, owner):
        return functools.partial(self.__call__, instance)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await concurrency.run(self.call_function, scope, receive, send)

    async def _http_function(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs an HTTP request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        :return: None.
        """
        app = scope["app"]
        scope["path"] = scope.get("root_path", "").rstrip("/") + scope["path"]
        scope["root_path"] = ""
        route, route_scope = app.router.resolve_route(scope)
        state = {
            "scope": route_scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "root_app": scope["root_app"],
            "path_params": route_scope.get("path_params", {}),
            "route": route,
            "request": http.Request(route_scope, receive=receive),
        }

        try:
            injected_func = await app.injector.inject(self.handler, state)
            response = await concurrency.run(injected_func)
            response = self._build_api_response(self.handler, response)
        except Exception:
            logger.exception("Error performing request")
            raise

        await response(route_scope, receive, send)

    async def _http_endpoint(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs an HTTP request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        :return: None.
        """
        response = await self.handler(scope, receive, send)
        response = self._build_api_response(self.handler, response)

        await response(scope, receive, send)

    async def _websocket_function(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a websocket request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        :return: None.
        """
        app = scope["app"]
        scope["path"] = scope.get("root_path", "").rstrip("/") + scope["path"]
        scope["root_path"] = ""
        route, route_scope = app.router.resolve_route(scope)
        state = {
            "scope": route_scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "root_app": scope["root_app"],
            "path_params": route_scope.get("path_params", {}),
            "route": route,
            "websocket": websockets.WebSocket(route_scope, receive, send),
            "websocket_encoding": None,
            "websocket_code": None,
            "websocket_message": None,
        }

        injected_func = await app.injector.inject(self.handler, state)
        await injected_func(**route_scope.get("kwargs", {}))

    async def _websocket_endpoint(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a websocket request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        :return: None.
        """
        await self.handler(scope, receive, send)

    def _build_api_response(self, handler: t.Callable, response: t.Union[http.Response, None]) -> http.Response:
        """Build an API response given a handler and the current response.

        It infers the output schema from the handler signature or just wraps the response in a APIResponse object.

        :param handler: The handler in charge of the request.
        :param response: The current response.
        :return: An API response.
        """
        if isinstance(response, (dict, list)):
            try:
                schema = schemas.Schema.from_type(inspect.signature(handler).return_annotation).unique_schema
            except Exception:
                schema = None

            response = http.APIResponse(content=response, schema=schema)
        elif isinstance(response, str):
            response = http.APIResponse(content=response)
        elif response is None:
            response = http.APIResponse(content="")

        return response

    def __eq__(self, other) -> bool:
        return isinstance(other, EndpointWrapper) and self.handler == other.handler


class BaseRoute(abc.ABC, RouteParametersMixin):
    def __init__(
        self,
        path: t.Union[str, url.RegexPath],
        app: types.App,
        *,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        tags: t.Optional[dict[str, t.Any]] = None,
    ):
        """A route definition of a http endpoint.

        :param path: URL path.
        :param app: ASGI application.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param tags: Route tags.
        """
        self.path = url.RegexPath(path)
        self.app = app
        self.endpoint = app.handler if isinstance(app, EndpointWrapper) else app
        self.name = name
        self.include_in_schema = include_in_schema
        self.tags = tags or {}
        super().__init__()

    @abc.abstractmethod
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        ...

    def __eq__(self, other: t.Any) -> bool:
        return (
            isinstance(other, BaseRoute)
            and self.path == other.path
            and self.app == other.app
            and self.name == other.name
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r}, name={(self.name or '')!r})"

    def build(self, app: t.Optional["Flama"] = None) -> None:
        """Build step for routes.

        Just build the parameters' descriptor part of RouteParametersMixin.

        :param app: Flama app.
        """
        if app:
            self.parameters.build(app)

    def endpoint_handlers(self) -> dict[str, t.Callable]:
        """Return a mapping of all possible endpoints of this route.

        Useful to identify all endpoints by HTTP methods.

        :return: Mapping of all endpoints.
        """
        return {}

    async def handle(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request by calling the app of this route.

        :param scope: ASGI scope.
        :param receive: ASGI receive event.
        :param send: ASGI send event.
        """
        await concurrency.run(self.app, scope, receive, send)

    def match(self, scope: types.Scope) -> Match:
        """Check if this route matches with given scope.

        :param scope: ASGI scope.
        :return: Match.
        """
        return Match.full if self.path.match(scope["path"]) else Match.none

    def route_scope(self, scope: types.Scope) -> types.Scope:
        """Build route scope from given scope.

        :param scope: ASGI scope.
        :return: Route scope.
        """
        return types.Scope(
            {
                "endpoint": self.endpoint,
                "path_params": {**dict(scope.get("path_params", {})), **self.path.values(scope["path"])},
            }
        )

    def resolve_url(self, name: str, **params: t.Any) -> url.URL:
        """Builds URL path for given name and params.

        :param name: Route name.
        :param params: Path params.
        :return: URL path.
        """
        if name != self.name:
            raise exceptions.NotFoundException(params=params, name=name)

        try:
            path, remaining_params = self.path.build(**params)
            assert not remaining_params or set(remaining_params.keys()) == {"path"}
        except (ValueError, AssertionError):
            raise exceptions.NotFoundException(params=params, name=name)

        return url.URL(path=path, scheme="http")


class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: t.Union[t.Callable, type[endpoints.HTTPEndpoint]],
        *,
        methods: t.Optional[t.Union[set[str], t.Sequence[str]]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> None:
        """A route definition of a http endpoint.

        :param path: URL path.
        :param endpoint: HTTP endpoint or function.
        :param methods: List of valid HTTP methods.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param pagination: Apply a pagination technique.
        :param tags: Route tags.
        """
        assert self.is_endpoint(endpoint) or (
            not inspect.isclass(endpoint) and callable(endpoint)
        ), "Endpoint must be a callable or an HTTPEndpoint subclass"

        if self.is_endpoint(endpoint):
            self.methods = endpoint.allowed_methods() if methods is None else set(methods)
        else:
            self.methods = {"GET"} if methods is None else set(methods)

        if "GET" in self.methods:
            self.methods.add("HEAD")

        name = endpoint.__name__ if name is None else name

        super().__init__(
            path,
            EndpointWrapper(endpoint, EndpointWrapper.type.http, pagination=pagination),
            name=name,
            include_in_schema=include_in_schema,
            tags=tags,
        )

        self.app: EndpointWrapper

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] == "http":
            await self.handle(types.Scope({**scope, **self.route_scope(scope)}), receive, send)

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, Route) and self.methods == other.methods

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r}, name={self.name!r}, methods={sorted(self.methods)!r})"

    @staticmethod
    def is_endpoint(
        x: t.Union[t.Callable, type[endpoints.HTTPEndpoint]]
    ) -> compat.TypeGuard[type[endpoints.HTTPEndpoint]]:  # PORT: Replace compat when stop supporting 3.9
        return inspect.isclass(x) and issubclass(x, endpoints.HTTPEndpoint)

    def endpoint_handlers(self) -> dict[str, t.Callable]:
        """Return a mapping of all possible endpoints of this route.

        Useful to identify all endpoints by HTTP methods.

        :return: Mapping of all endpoints.
        """
        if self.is_endpoint(self.endpoint):
            return {
                method: handler
                for method, handler in self.endpoint.allowed_handlers().items()
                if method in self.methods
            }

        return {method: self.endpoint for method in self.methods}

    def match(self, scope: types.Scope) -> Match:
        """Check if this route matches with given scope.

        :param scope: ASGI scope.
        :return: Match.
        """
        if scope["type"] != "http":
            return Match.none

        m = super().match(scope)
        if m == Match.none:
            return m

        return Match.full if scope["method"] in self.methods else Match.partial


class WebSocketRoute(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: t.Union[t.Callable, type[endpoints.WebSocketEndpoint]],
        *,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
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

        assert self.is_endpoint(endpoint) or (
            not inspect.isclass(endpoint) and callable(endpoint)
        ), "Endpoint must be a callable or a WebSocketEndpoint subclass"

        name = endpoint.__name__ if name is None else name

        super().__init__(
            path,
            EndpointWrapper(endpoint, EndpointWrapper.type.websocket, pagination=pagination),
            name=name,
            include_in_schema=include_in_schema,
            tags=tags,
        )

        self.app: EndpointWrapper

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] == "websocket":
            await self.handle(types.Scope({**scope, **self.route_scope(scope)}), receive, send)

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, WebSocketRoute)

    @staticmethod
    def is_endpoint(
        x: t.Union[t.Callable, type[endpoints.WebSocketEndpoint]]
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

    def match(self, scope: types.Scope) -> Match:
        """Check if this route matches with given scope.

        :param scope: ASGI scope.
        :return: Match.
        """
        if scope["type"] != "websocket":
            return Match.none

        return super().match(scope)


class Mount(BaseRoute):
    def __init__(
        self,
        path: str,
        app: t.Optional[types.App] = None,
        *,
        routes: t.Optional[t.Sequence[BaseRoute]] = None,
        components: t.Optional[t.Sequence[Component]] = None,
        name: t.Optional[str] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ):
        """A mount point for adding a nested ASGI application or a list of routes.

        :param path: URL path.
        :param app: ASGI application.
        :param routes: List of routes.
        :param components: Components registered under this mount point.
        :param name: Mount name.
        :param tags: Mount tags.
        """
        assert app is not None or routes is not None, "Either 'app' or 'routes' must be specified"

        if app is None:
            app = Router(routes=routes, components=components)

        super().__init__(url.RegexPath(path.rstrip("/") + "{path:path}"), app, name=name, tags=tags)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] in ("http", "websocket") or (
            scope["type"] == "lifespan" and types.is_flama_instance(self.app)
        ):
            await self.handle(types.Scope({**scope, **self.route_scope(scope)}), receive, send)

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, Mount)

    def build(self, app: t.Optional["Flama"] = None) -> None:
        """Build step for routes.

        Just build the parameters' descriptor part of RouteParametersMixin.

        :param app: Flama app.
        """
        if app and types.is_flama_instance(self.app):
            self.app.router.components = Components(self.app.router.components + app.components)

        if root := (self.app if types.is_flama_instance(self.app) else app):
            for route in self.routes:
                route.build(root)

    def match(self, scope: types.Scope) -> Match:
        """Check if this route matches with given scope.

        :param scope: ASGI scope.
        :return: Match.
        """
        if scope["type"] not in ("http", "websocket"):
            return Match.none

        return super().match(scope)

    async def handle(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request by calling the app of this route.

        :param scope: ASGI scope.
        :param receive: ASGI receive event.
        :param send: ASGI send event
        """
        await concurrency.run(self.app, scope, receive, send)

    def route_scope(self, scope: types.Scope) -> types.Scope:
        """Build route scope from given scope.

        It generates an updated scope parameters for the route:
        * app: The app of this mount point. If it's mounting a Flama app, it will replace the app with this one
        * path_params: The matched path parameters of this mount point
        * endpoint: The endpoint of this mount point
        * root_path: The root path of this mount point (if it's mounting a Flama app, it will be empty)
        * path: The remaining path to be matched

        :param scope: ASGI scope.
        :return: Route scope.
        """
        result = {"app": self.app if types.is_flama_instance(self.app) else scope["app"]}

        if "path" in scope:
            path = scope["path"]
            matched_params = self.path.values(path)
            remaining_path = matched_params.pop("path")
            matched_path = path[: -len(remaining_path)]
            result.update(
                {
                    "path_params": {**dict(scope.get("path_params", {})), **matched_params},
                    "endpoint": self.endpoint,
                    "root_path": "" if types.is_flama_instance(self.app) else scope.get("root_path", "") + matched_path,
                    "path": remaining_path,
                }
            )

        return types.Scope(result)

    def resolve_url(self, name: str, **params: t.Any) -> url.URL:
        """Builds URL path for given name and params.

        :param name: Route name.
        :param params: Path params.
        :return: URL path.
        """
        if self.name is not None and name == self.name and "path" in params:
            return super().resolve_url(name, **{**params, "path": params["path"].lstrip("/")})
        elif self.name is None or name.startswith(f"{self.name}:"):
            remaining_name = name if self.name is None else name.split(":", 1)[1]
            path, remaining_params = self.path.build(**{**params, "path": ""})
            if "path" in params:
                remaining_params["path"] = params["path"]
            else:
                del remaining_params["path"]
            for route in self.routes:
                try:
                    route_url = route.resolve_url(remaining_name, **remaining_params)
                    route_url.path = f"{path.rstrip('/')}{route_url.path}"
                    return route_url
                except exceptions.NotFoundException:
                    pass
        raise exceptions.NotFoundException(params=params, name=name)

    @property
    def routes(self) -> list[BaseRoute]:
        """Get all routes registered in this Mount.

        :return: List of routes.
        """
        return getattr(self.app, "routes", [])


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

    def __eq__(self, other: t.Any) -> bool:
        return isinstance(other, Router) and self.routes == other.routes

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        logger.debug("Request: %s", str(scope))
        assert scope["type"] in ("http", "websocket", "lifespan")

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
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
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

        assert route is not None, "Either 'path' and 'endpoint' or 'route' variables are needed"

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
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
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
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
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

        assert route is not None, "Either 'path' and 'endpoint' or 'route' variables are needed"

        self.routes.append(route)

        route.build(root)

        return route

    def websocket_route(
        self,
        path: str,
        name: t.Optional[str] = None,
        *,
        root: t.Optional["Flama"] = None,
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
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

        assert mount is not None, "Either 'path' and 'app' or 'mount' variables are needed"

        self.routes.append(mount)

        mount.build(root)

        return mount

    def resolve_route(self, scope: types.Scope) -> tuple[BaseRoute, types.Scope]:
        """Look for a route that matches given ASGI scope.

        :param scope: ASGI scope.
        :return: Route and its scope.
        """
        partial = None
        partial_allowed_methods: set[str] = set()

        for route in self.routes:
            m = route.match(scope)
            if m == Match.full:
                route_scope = types.Scope({**scope, **route.route_scope(scope)})

                if isinstance(route, Mount):
                    try:
                        return route.app.resolve_route(route_scope)  # type: ignore[no-any-return,union-attr]
                    except AttributeError:
                        ...

                return route, route_scope
            elif m == Match.partial:
                partial = route
                if isinstance(route, Route):
                    partial_allowed_methods |= route.methods

        if partial:
            route_scope = types.Scope({**scope, **partial.route_scope(scope)})
            raise exceptions.MethodNotAllowedException(
                route_scope.get("root_path", "") + route_scope["path"],
                route_scope["method"],
                partial_allowed_methods,
                params=route_scope.get("path_params"),
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
