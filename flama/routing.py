import enum
import functools
import inspect
import logging
import sys
import typing as t

from flama import concurrency, endpoints, exceptions, http, types, url, websockets
from flama.injection import Component, Components
from flama.lifespan import Lifespan
from flama.schemas.routing import RouteParametersMixin
from flama.schemas.validation import get_output_schema

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard
else:  # pragma: no cover
    from typing_extensions import TypeGuard

if t.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["Route", "WebSocketRoute", "Mount", "Router"]

logger = logging.getLogger(__name__)


class EndpointType(enum.Enum):
    http = enum.auto()
    websocket = enum.auto()


class Match(enum.Enum):
    none = enum.auto()
    partial = enum.auto()
    full = enum.auto()


class EndpointWrapper(types.AppClass):
    def __init__(
        self,
        handler: t.Union[types.AppFunction, t.Type[endpoints.HTTPEndpoint], t.Type[endpoints.WebSocketEndpoint]],
        endpoint_type: EndpointType,
    ):
        """Wraps a function or endpoint into ASGI application.

        :param handler: Function or endpoint.
        """

        self.handler = handler
        functools.update_wrapper(self, handler)
        self.call_function: types.App = {
            (EndpointType.http, False): self._http_function,
            (EndpointType.http, True): self._http_endpoint,
            (EndpointType.websocket, False): self._websocket_function,
            (EndpointType.websocket, True): self._websocket_endpoint,
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
            response = http.APIResponse(content=response, schema=get_output_schema(handler))
        elif isinstance(response, str):
            response = http.APIResponse(content=response)
        elif response is None:
            response = http.APIResponse(content="")

        return response


class BaseRoute(RouteParametersMixin):
    def __init__(
        self,
        path: t.Union[str, url.RegexPath],
        app: types.App,
        *,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        main_app: t.Optional["Flama"] = None,
    ):
        self.path = url.RegexPath(path) if isinstance(path, str) else path
        self.app = app
        self.endpoint = app.handler if isinstance(app, EndpointWrapper) else app
        if name is None:
            self.name = (
                app.__name__  # type: ignore[union-attr]
                if inspect.isroutine(self.endpoint) or inspect.isclass(self.endpoint)
                else self.endpoint.__class__.__name__
            )
        else:
            self.name = name
        self.include_in_schema = include_in_schema
        self.main_app = main_app

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await self.handle(types.Scope({**scope, **self.route_scope(scope)}), receive, send)

    def __eq__(self, other: t.Any) -> bool:
        return isinstance(other, BaseRoute) and self.path == other.path and self.app == other.app

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r}, name={(self.name or '')!r})"

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
                "path_params": {**dict(scope.get("path_params", {})), **self.path.params(scope["path"])},
            }
        )

    def resolve_url(self, name: str, **params: t.Any) -> url.URL:
        """Builds URL path for given name and params.

        :param name: Route name.
        :param params: Path params.
        :return: URL path.
        """
        if name != self.name or set(params.keys()) != set(self.path.serializers.keys()):
            raise exceptions.NotFoundException(params=params, name=name)

        path, remaining_params = self.path.build(**params)
        assert not remaining_params

        return url.URL(path=path, scheme="http")

    @property
    def main_app(self) -> t.Optional["Flama"]:  # pragma: no cover
        return self._main_app

    @main_app.setter
    def main_app(self, app: t.Optional["Flama"]):  # pragma: no cover
        self._main_app = app

        try:
            self.app.main_app = app  # type: ignore[union-attr]
        except AttributeError:
            ...

        try:
            self.app.app.main_app = app  # type: ignore[union-attr]
        except AttributeError:
            ...

        try:
            for route in getattr(self, "routes"):
                route.main_app = app
        except AttributeError:
            ...

    @main_app.deleter
    def main_app(self):  # pragma: no cover
        try:
            del self._main_app
        except AttributeError:
            ...

        try:
            del self.app.main_app
        except AttributeError:
            ...

        try:
            del self.app.app.main_app
        except AttributeError:
            ...

        try:
            for route in self.routes:
                del route.main_app
        except AttributeError:
            ...


class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: t.Union[types.AppFunction, t.Type[endpoints.HTTPEndpoint]],
        *,
        methods: t.Optional[t.List[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        main_app: t.Optional["Flama"] = None,
    ) -> None:
        """A route definition of a http endpoint.

        :param path: URL path.
        :param endpoint: HTTP endpoint or function.
        :param methods: List of valid HTTP methods.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param main_app: Flama app.
        """

        def is_endpoint(
            x: t.Union[types.AppFunction, t.Type[endpoints.HTTPEndpoint]]
        ) -> TypeGuard[t.Type[endpoints.HTTPEndpoint]]:
            return inspect.isclass(x) and issubclass(x, endpoints.HTTPEndpoint)

        assert is_endpoint(endpoint) or callable(endpoint), "Endpoint must be a callable or an HTTPEndpoint subclass"

        if methods is None:
            self.methods = endpoint.allowed_methods() if is_endpoint(endpoint) else {"GET"}
        else:
            self.methods = set(methods)

        if "GET" in self.methods:
            self.methods.add("HEAD")

        super().__init__(
            path,
            EndpointWrapper(endpoint, EndpointType.http),
            name=name,
            include_in_schema=include_in_schema,
            main_app=main_app,
        )

        self.app: EndpointWrapper

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, Route) and self.methods == other.methods

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r}, name={self.name!r}, methods={sorted(self.methods)!r})"

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
        endpoint: t.Union[types.AppFunction, t.Type[endpoints.WebSocketEndpoint]],
        *,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        main_app: t.Optional["Flama"] = None,
    ):
        """A route definition of a websocket endpoint.

        :param path: URL path.
        :param endpoint: Websocket endpoint or function.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param main_app: Flama app.
        """

        def is_endpoint(
            x: t.Union[types.AppFunction, t.Type[endpoints.WebSocketEndpoint]]
        ) -> TypeGuard[t.Type[endpoints.WebSocketEndpoint]]:
            return inspect.isclass(x) and issubclass(x, endpoints.WebSocketEndpoint)

        assert is_endpoint(endpoint) or callable(
            endpoint
        ), "Endpoint must be a callable or a WebSocketEndpoint subclass"

        super().__init__(
            path,
            EndpointWrapper(endpoint, EndpointType.websocket),
            name=name,
            include_in_schema=include_in_schema,
            main_app=main_app,
        )

        self.app: EndpointWrapper

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, WebSocketRoute)

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
        name: str = None,
        main_app: t.Optional["Flama"] = None,
    ):
        assert app is not None or routes is not None, "Either 'app' or 'routes' must be specified"

        if app is None:
            app = Router(routes=routes, components=components)

        super().__init__(url.RegexPath(path.rstrip("/") + "{path:path}"), app, name=name, main_app=main_app)

    def __eq__(self, other: t.Any) -> bool:
        return super().__eq__(other) and isinstance(other, Mount)

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
        matched_params = self.path.params(path)
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
            for route in self.routes:
                try:
                    route_url = route.resolve_url(remaining_name, **remaining_params)
                    return url.URL(path=f"{path.rstrip('/')}{url!s}", scheme=route_url.scheme)
                except exceptions.NotFoundException:
                    pass
        raise exceptions.NotFoundException(params=params, name=name)

    @property
    def routes(self) -> t.List[BaseRoute]:
        """Get all routes registered in this Mount.

        :return: List of routes.
        """
        return getattr(self.app, "routes", [])


class Router(types.AsyncAppClass):
    def __init__(
        self,
        routes: t.Optional[t.Sequence[BaseRoute]] = None,
        *,
        components: t.Optional[t.Sequence["Component"]] = None,
        lifespan: t.Optional[t.Callable[[t.Optional["Flama"]], t.AsyncContextManager]] = None,
        main_app: t.Optional["Flama"] = None,
    ):
        self.routes = [] if routes is None else list(routes)
        self._components = Components(components if components else set())
        self.lifespan = Lifespan(lifespan)
        self.main_app = main_app

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

    @property
    def main_app(self) -> t.Optional["Flama"]:
        return self._main_app

    @main_app.setter
    def main_app(self, app: t.Optional["Flama"]):
        self._main_app = app

        if app is not None:
            for route in self.routes:
                route.main_app = app

    @main_app.deleter
    def main_app(self):
        del self._main_app

        for route in self.routes:
            del route.main_app

    @property
    def components(self) -> Components:
        return Components(
            self._components
            + [
                component
                for route in self.routes
                if hasattr(route, "app") and hasattr(route.app, "components")
                for component in getattr(route.app, "components", [])
            ]
        )

    def add_component(self, component: Component):
        """Register a new component.

        :param component: Component to register.
        """
        self._components.append(component)

    def mount(
        self, path: t.Optional[str] = None, app: t.Optional[types.App] = None, name: str = None, mount: Mount = None
    ) -> Mount:
        """Register a new mount point containing an ASGI app in this router under given path.

        :param path: URL path.
        :param app: ASGI app to mount.
        :param name: Route name.
        :param mount: Mount.
        :return: Mount.
        """
        if path is not None and app is not None:
            mount = Mount(path, app=app, name=name, main_app=self.main_app)
        elif mount is not None:
            mount.main_app = self.main_app
        else:
            raise ValueError("Either 'path' and 'app' or 'mount' variables are needed")

        self.routes.append(mount)

        return mount

    def add_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.HTTPHandler] = None,
        methods: t.List[str] = None,
        name: str = None,
        include_in_schema: bool = True,
        route: Route = None,
    ) -> Route:
        """Register a new HTTP route in this router under given path.

        :param path: URL path.
        :param endpoint: HTTP endpoint.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param route: HTTP route.
        :return: Route.
        """
        if path is not None and endpoint is not None:
            route = Route(
                path,
                endpoint=endpoint,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
                main_app=self.main_app,
            )
        elif route is not None:
            route.main_app = self.main_app
        else:
            raise ValueError("Either 'path' and 'endpoint' or 'route' variables are needed")

        self.routes.append(route)

        return route

    def route(
        self, path: str, methods: t.List[str] = None, name: str = None, include_in_schema: bool = True
    ) -> t.Callable[[types.HTTPHandler], types.HTTPHandler]:
        """Decorator version for registering a new HTTP route in this router under given path.

        :param path: URL path.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :return: Decorated route.
        """

        def decorator(func: types.HTTPHandler) -> types.HTTPHandler:
            self.add_route(path, func, methods=methods, name=name, include_in_schema=include_in_schema)
            return func

        return decorator

    def add_websocket_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.WebSocketHandler] = None,
        name: str = None,
        route: t.Optional[WebSocketRoute] = None,
    ) -> WebSocketRoute:
        """Register a new websocket route in this router under given path.

        :param path: URL path.
        :param endpoint: Websocket function or endpoint.
        :param name: Websocket route name.
        :param route: Specific route class.
        :return: Websocket route.
        """
        if path is not None and endpoint is not None:
            route = WebSocketRoute(path, endpoint=endpoint, name=name, main_app=self.main_app)
        elif route is not None:
            route.main_app = self.main_app
        else:
            raise ValueError("Either 'path' and 'endpoint' or 'route' variables are needed")

        self.routes.append(route)

        return route

    def websocket_route(
        self, path: str, name: str = None
    ) -> t.Callable[[types.WebSocketHandler], types.WebSocketHandler]:
        """Decorator version for registering a new websocket route in this router under given path.

        :param path: URL path.
        :param name: Websocket route name.
        :return: Decorated websocket route.
        """

        def decorator(func: types.WebSocketHandler) -> types.WebSocketHandler:
            self.add_websocket_route(path, func, name=name)
            return func

        return decorator

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

                if isinstance(route, Mount) and isinstance(route.app, Router):
                    return route.app.resolve_route(route_scope)

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
