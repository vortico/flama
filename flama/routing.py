import enum
import functools
import inspect
import logging
import sys
import typing as t

from flama import concurrency, endpoints, exceptions, http, schemas, types, url, websockets
from flama.injection import Component, Components
from flama.lifespan import Lifespan
from flama.schemas.routing import RouteParametersMixin

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard

    t.TypeGuard = TypeGuard

if t.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["Route", "WebSocketRoute", "Mount", "Router"]

logger = logging.getLogger(__name__)


class _EndpointType(enum.Enum):
    http = enum.auto()
    websocket = enum.auto()


class Match(enum.Enum):
    none = enum.auto()
    partial = enum.auto()
    full = enum.auto()


class EndpointWrapper(types.AppAsyncClass):
    type = _EndpointType

    def __init__(
        self,
        handler: t.Union[t.Callable, t.Type[endpoints.HTTPEndpoint], t.Type[endpoints.WebSocketEndpoint]],
        endpoint_type: _EndpointType,
    ):
        """Wraps a function or endpoint into ASGI application.

        :param handler: Function or endpoint.
        """

        self.handler = handler
        functools.update_wrapper(self, handler)
        self.call_function: types.App = {
            (self.type.http, False): self._http_function,
            (self.type.http, True): self._http_endpoint,
            (self.type.websocket, False): self._websocket_function,
            (self.type.websocket, True): self._websocket_endpoint,
        }[(endpoint_type, inspect.isclass(self.handler))]

    def __get__(self, instance, owner):
        return functools.partial(self.__call__, instance)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await self.call_function(scope, receive, send)

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
            "path_params": route_scope.get("path_params", {}),
            "route": route,
            "request": http.Request(route_scope, receive=receive),
        }

        try:
            injected_func = await app.injector.inject(self.handler, **state)
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
            "path_params": route_scope.get("path_params", {}),
            "route": route,
            "websocket": websockets.WebSocket(route_scope, receive, send),
            "websocket_encoding": None,
            "websocket_code": None,
            "websocket_message": None,
        }

        injected_func = await app.injector.inject(self.handler, **state)
        await injected_func(**route_scope.get("kwargs", {}))

    async def _websocket_endpoint(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a websocket request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        :return: None.
        """
        await self.handler(scope, receive, send)

    def _build_api_response(self, handler: t.Callable, response: http.Response) -> http.Response:
        """Build an API response given a handler and the current response.

        It infers the output schema from the handler signature or just wraps the response in a APIResponse object.

        :param handler: The handler in charge of the request.
        :param response: The current response.
        :return: An API response.
        """
        if isinstance(response, (dict, list)):
            try:
                schema = schemas.Schema.from_type(inspect.signature(handler).return_annotation).schema
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


class BaseRoute(RouteParametersMixin):
    def __init__(
        self,
        path: t.Union[str, url.RegexPath],
        app: types.App,
        *,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
    ):
        """A route definition of a http endpoint.

        :param path: URL path.
        :param app: ASGI application.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        """
        self.path = url.RegexPath(path)
        self.app = app
        self.endpoint = app.handler if isinstance(app, EndpointWrapper) else app
        self.name = name
        self.include_in_schema = include_in_schema
        super().__init__()

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await self.handle(types.Scope({**scope, **self.route_scope(scope)}), receive, send)

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

    def endpoint_handlers(self) -> t.Dict[str, t.Callable]:
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
        await self.app(scope, receive, send)

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
        endpoint: t.Union[t.Callable, t.Type[endpoints.HTTPEndpoint]],
        *,
        methods: t.Optional[t.Union[t.Set[str], t.Sequence[str]]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
    ) -> None:
        """A route definition of a http endpoint.

        :param path: URL path.
        :param endpoint: HTTP endpoint or function.
        :param methods: List of valid HTTP methods.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
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
            path, EndpointWrapper(endpoint, EndpointWrapper.type.http), name=name, include_in_schema=include_in_schema
        )

        self.app: EndpointWrapper

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, Route) and self.methods == other.methods

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r}, name={self.name!r}, methods={sorted(self.methods)!r})"

    @staticmethod
    def is_endpoint(
        x: t.Union[t.Callable, t.Type[endpoints.HTTPEndpoint]]
    ) -> t.TypeGuard[t.Type[endpoints.HTTPEndpoint]]:
        return inspect.isclass(x) and issubclass(x, endpoints.HTTPEndpoint)

    def endpoint_handlers(self) -> t.Dict[str, t.Callable]:
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
        endpoint: t.Union[t.Callable, t.Type[endpoints.WebSocketEndpoint]],
        *,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
    ):
        """A route definition of a websocket endpoint.

        :param path: URL path.
        :param endpoint: Websocket endpoint or function.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        """

        assert self.is_endpoint(endpoint) or (
            not inspect.isclass(endpoint) and callable(endpoint)
        ), "Endpoint must be a callable or a WebSocketEndpoint subclass"

        name = endpoint.__name__ if name is None else name

        super().__init__(
            path,
            EndpointWrapper(endpoint, EndpointWrapper.type.websocket),
            name=name,
            include_in_schema=include_in_schema,
        )

        self.app: EndpointWrapper

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, WebSocketRoute)

    @staticmethod
    def is_endpoint(
        x: t.Union[t.Callable, t.Type[endpoints.WebSocketEndpoint]]
    ) -> t.TypeGuard[t.Type[endpoints.WebSocketEndpoint]]:
        return inspect.isclass(x) and issubclass(x, endpoints.WebSocketEndpoint)

    def endpoint_handlers(self) -> t.Dict[str, t.Callable]:
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
    ):
        """A mount point for adding a nested ASGI application or a list of routes.

        :param path: URL path.
        :param app: ASGI application.
        :param routes: List of routes.
        :param components: Components registered under this mount point.
        :param name: Mount name.
        """
        assert app is not None or routes is not None, "Either 'app' or 'routes' must be specified"

        if app is None:
            app = Router(routes=routes, components=components)

        super().__init__(url.RegexPath(path.rstrip("/") + "{path:path}"), app, name=name)

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, Mount)

    def build(self, app: t.Optional["Flama"] = None) -> None:
        """Build step for routes.

        Just build the parameters' descriptor part of RouteParametersMixin.

        :param app: Flama app.
        """
        if app:
            for route in self.routes:
                route.build(app)

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
        await self.app(scope, receive, send)

    def route_scope(self, scope: types.Scope) -> types.Scope:
        """Build route scope from given scope.

        :param scope: ASGI scope.
        :return: Route scope.
        """
        path = scope["path"]
        root_path = scope.get("root_path", "")
        matched_params = self.path.values(path)
        remaining_path = matched_params.pop("path")
        matched_path = path[: -len(remaining_path)]
        return types.Scope(
            {
                "path_params": {**dict(scope.get("path_params", {})), **matched_params},
                "endpoint": self.endpoint,
                "root_path": root_path + matched_path,
                "path": remaining_path,
            }
        )

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
    def routes(self) -> t.List[BaseRoute]:
        """Get all routes registered in this Mount.

        :return: List of routes.
        """
        return getattr(self.app, "routes", [])


class Router(types.AppAsyncClass):
    def __init__(
        self,
        routes: t.Optional[t.Sequence[BaseRoute]] = None,
        *,
        components: t.Optional[t.Sequence["Component"]] = None,
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
        self._components = Components(components if components else set())
        self.lifespan = Lifespan(lifespan)

        if root:
            self.build(root)

    def __eq__(self, other: t.Any) -> bool:
        return isinstance(other, Router) and self.routes == other.routes

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        assert scope["type"] in ("http", "websocket", "lifespan")

        if "router" not in scope:
            scope["router"] = self

        if scope["type"] == "lifespan":
            await self.lifespan(scope, receive, send)
            return

        route, route_scope = self.resolve_route(scope)
        await route(route_scope, receive, send)

    def build(self, app: "Flama") -> None:
        """Build step for routes.

        Just build the parameters' descriptor part of RouteParametersMixin.

        :param app: Flama app.
        """
        for route in self.routes:
            route.build(app)

    @property
    def components(self) -> Components:
        return Components(
            self._components
            + Components(
                [
                    component
                    for route in self.routes
                    if hasattr(route, "app") and hasattr(route.app, "components")
                    for component in getattr(route.app, "components", [])
                ]
            )
        )

    def add_component(self, component: Component):
        """Register a new component.

        :param component: Component to register.
        """
        self._components = Components(self._components + Components([component]))

    def add_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.HTTPHandler] = None,
        methods: t.Optional[t.List[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        route: t.Optional[Route] = None,
        root: t.Optional["Flama"] = None,
    ) -> Route:
        """Register a new HTTP route in this router under given path.

        :param path: URL path.
        :param endpoint: HTTP endpoint.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param route: HTTP route.
        :param root: Flama application.
        :return: Route.
        """
        if path is not None and endpoint is not None:
            route = Route(path, endpoint=endpoint, methods=methods, name=name, include_in_schema=include_in_schema)

        assert route is not None, "Either 'path' and 'endpoint' or 'route' variables are needed"

        self.routes.append(route)

        route.build(root)

        return route

    def route(
        self,
        path: str,
        methods: t.Optional[t.List[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        root: t.Optional["Flama"] = None,
    ) -> t.Callable[[types.HTTPHandler], types.HTTPHandler]:
        """Decorator version for registering a new HTTP route in this router under given path.

        :param path: URL path.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param root: Flama application.
        :return: Decorated route.
        """

        def decorator(func: types.HTTPHandler) -> types.HTTPHandler:
            self.add_route(path, func, methods=methods, name=name, include_in_schema=include_in_schema, root=root)
            return func

        return decorator

    def add_websocket_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.WebSocketHandler] = None,
        name: t.Optional[str] = None,
        route: t.Optional[WebSocketRoute] = None,
        root: t.Optional["Flama"] = None,
    ) -> WebSocketRoute:
        """Register a new websocket route in this router under given path.

        :param path: URL path.
        :param endpoint: Websocket function or endpoint.
        :param name: Websocket route name.
        :param route: Specific route class.
        :param root: Flama application.
        :return: Websocket route.
        """
        if path is not None and endpoint is not None:
            route = WebSocketRoute(path, endpoint=endpoint, name=name)

        assert route is not None, "Either 'path' and 'endpoint' or 'route' variables are needed"

        self.routes.append(route)

        route.build(root)

        return route

    def websocket_route(
        self, path: str, name: t.Optional[str] = None, root: t.Optional["Flama"] = None
    ) -> t.Callable[[types.WebSocketHandler], types.WebSocketHandler]:
        """Decorator version for registering a new websocket route in this router under given path.

        :param path: URL path.
        :param name: Websocket route name.
        :param root: Flama application.
        :return: Decorated websocket route.
        """

        def decorator(func: types.WebSocketHandler) -> types.WebSocketHandler:
            self.add_websocket_route(path, func, name=name, root=root)
            return func

        return decorator

    def mount(
        self,
        path: t.Optional[str] = None,
        app: t.Optional[types.App] = None,
        name: t.Optional[str] = None,
        mount: t.Optional[Mount] = None,
        root: t.Optional["Flama"] = None,
    ) -> Mount:
        """Register a new mount point containing an ASGI app in this router under given path.

        :param path: URL path.
        :param app: ASGI app to mount.
        :param name: Route name.
        :param mount: Mount.
        :param root: Flama application.
        :return: Mount.
        """
        if path is not None and app is not None:
            mount = Mount(path, app=app, name=name)

        assert mount is not None, "Either 'path' and 'app' or 'mount' variables are needed"

        self.routes.append(mount)

        mount.build(root)

        return mount

    def resolve_route(self, scope: types.Scope) -> t.Tuple[BaseRoute, types.Scope]:
        """Look for a route that matches given ASGI scope.

        :param scope: ASGI scope.
        :return: Route and its scope.
        """
        partial = None
        partial_allowed_methods: t.Set[str] = set()

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
