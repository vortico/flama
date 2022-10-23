import enum
import functools
import inspect
import logging
import typing as t
from http import HTTPStatus

import starlette.routing
from starlette.routing import Match

from flama import concurrency, endpoints, exceptions, http, types, websockets
from flama.injection import Component, Components
from flama.schemas.routing import RouteParametersMixin
from flama.schemas.validation import get_output_schema

if t.TYPE_CHECKING:
    from flama.applications import Flama
    from flama.lifespan import Lifespan

__all__ = ["Mount", "Route", "Router", "WebSocketRoute", "NotFound"]

logger = logging.getLogger(__name__)

EndpointType = enum.Enum("EndpointType", ["http", "websocket"])


class EndpointWrapper(types.AppClass):
    def __init__(
        self,
        handler: t.Union[t.Callable, t.Type[endpoints.HTTPEndpoint], t.Type[endpoints.WebSocketEndpoint]],
        endpoint_type: EndpointType,
    ):
        """Wraps a function or endpoint into ASGI application.

        :param handler: Function or endpoint.
        """

        self.handler = handler
        functools.update_wrapper(self, self.handler)
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
        route, route_scope = app.router.get_route_from_scope(scope)
        state = {
            "scope": scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "path_params": route_scope["path_params"],
            "route": route,
            "request": http.Request(scope, receive=receive),
        }

        try:
            injected_func = await app.injector.inject(self.handler, **state)
            response = await concurrency.run(injected_func)
            response = self._build_api_response(self.handler, response)
        except Exception:
            logger.exception("Error performing request")
            raise

        await response(scope, receive, send)

    async def _http_endpoint(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs an HTTP request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        :return: None.
        """
        endpoint = self.handler(scope, receive, send)

        response = await endpoint
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
        route, route_scope = app.router.get_route_from_scope(scope)
        state = {
            "scope": scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "path_params": route_scope["path_params"],
            "route": route,
            "websocket": websockets.WebSocket(scope, receive, send),
            "websocket_encoding": None,
            "websocket_code": None,
            "websocket_message": None,
        }

        injected_func = await app.injector.inject(self.handler, **state)
        await injected_func(**scope.get("kwargs", {}))

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


class BaseRoute(RouteParametersMixin, starlette.routing.BaseRoute):
    @property
    def main_app(self) -> "Flama":  # pragma: no cover
        try:
            return self._main_app
        except AttributeError:
            raise AttributeError(f"{self.__class__.__name__} is not initialized")

    @main_app.setter
    def main_app(self, app: "Flama"):  # pragma: no cover
        self._main_app = app

        try:
            self.app.main_app = app  # type: ignore[attr-defined]
        except AttributeError:
            ...

        try:
            self.app.app.main_app = app  # type: ignore[attr-defined]
        except AttributeError:
            ...

        try:
            for route in self.routes:  # type: ignore[attr-defined]
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
            del self.app.main_app  # type: ignore[attr-defined]
        except AttributeError:
            ...

        try:
            del self.app.app.main_app  # type: ignore[attr-defined]
        except AttributeError:
            ...

        try:
            for route in self.routes:  # type: ignore[attr-defined]
                del route.main_app
        except AttributeError:
            ...


class Route(BaseRoute, starlette.routing.Route):
    def __init__(
        self,
        path: str,
        endpoint: t.Union[types.AppFunction, endpoints.HTTPEndpoint, t.Type[endpoints.HTTPEndpoint]],
        main_app: t.Optional["Flama"] = None,
        **kwargs,
    ):
        """A route definition of a http endpoint.

        :param path: URL path.
        :param endpoint: HTTP endpoint or function.
        :param main_app: Flama app.
        """
        assert (inspect.isclass(endpoint) and issubclass(endpoint, endpoints.HTTPEndpoint)) or callable(
            endpoint
        ), "Endpoint must be a callable or an HTTPEndpoint subclass"

        super().__init__(path, endpoint=endpoint, **kwargs)

        if main_app is not None:
            self.main_app = main_app

        if self.methods is None:
            try:
                self.methods = endpoint.allowed_methods()  # type: ignore[union-attr]
            except AttributeError:
                raise AssertionError("Must define valid http methods")

        self.app: EndpointWrapper = EndpointWrapper(endpoint, EndpointType.http)  # type: ignore[assignment]


class WebSocketRoute(BaseRoute, starlette.routing.WebSocketRoute):
    def __init__(
        self,
        path: str,
        endpoint: t.Union[t.Callable, endpoints.WebSocketEndpoint, t.Type[endpoints.WebSocketEndpoint]],
        main_app: "Flama" = None,
        **kwargs,
    ):
        """A route definition of a websocket endpoint.

        :param path: URL path.
        :param endpoint: Websocket endpoint or function.
        :param main_app: Flama app.
        """
        assert (inspect.isclass(endpoint) and issubclass(endpoint, endpoints.WebSocketEndpoint)) or callable(
            endpoint
        ), "Endpoint must be a callable or a WebSocketEndpoint subclass"

        super().__init__(path, endpoint=endpoint, **kwargs)

        if main_app is not None:
            self.main_app = main_app

        self.app: EndpointWrapper = EndpointWrapper(endpoint, EndpointType.websocket)  # type: ignore[assignment]


class Mount(BaseRoute, starlette.routing.Mount):
    def __init__(
        self,
        path: str,
        main_app: "Flama" = None,
        app: types.App = None,
        routes: t.Sequence[BaseRoute] = None,
        components: t.Optional[t.Set[Component]] = None,
        name: str = None,
    ):
        if app is None:
            app = Router(routes=routes, components=components)  # type: ignore[assignment]

        super().__init__(path, app, routes, name)  # type: ignore[arg-type]

        if main_app is not None:
            self.main_app = main_app

    @property
    def routes(self) -> t.List[BaseRoute]:  # type: ignore[override]
        return getattr(self.app, "routes", [])


class Router(starlette.routing.Router):
    def __init__(
        self,
        main_app: "Flama" = None,
        components: t.Optional[t.Set["Component"]] = None,
        routes: t.Sequence[BaseRoute] = None,
        lifespan: t.Optional["Lifespan"] = None,
        *args,
        **kwargs,
    ):
        self._components = Components(components.copy() if components else set())
        super().__init__(routes=routes, lifespan=lifespan, *args, **kwargs)  # type: ignore[misc]
        self.lifespan: t.Optional["Lifespan"]  # type: ignore[assignment]
        self.routes: t.List[BaseRoute] = list(self.routes)  # type: ignore[assignment]

        if main_app is not None:
            self.main_app = main_app

    async def __call__(  # type: ignore[override]
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> None:
        await super().__call__(scope, receive, send)  # type: ignore[arg-type]

    @property
    def main_app(self) -> "Flama":
        try:
            return self._main_app
        except AttributeError:
            raise AttributeError(f"{self.__class__.__name__} is not initialized")

    @main_app.setter
    def main_app(self, app: "Flama"):
        self._main_app = app

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
                if hasattr(route, "app") and hasattr(route.app, "components")  # type: ignore[attr-defined]
                for component in getattr(route.app, "components", [])  # type: ignore[attr-defined]
            ]
        )

    def add_component(self, component: Component):
        self._components.append(component)

    def mount(self, path: str, app: types.App, name: str = None) -> None:  # type: ignore[override]
        try:
            main_app = self.main_app
        except AttributeError:
            main_app = None

        self.routes.append(Mount(path.rstrip("/"), app=app, name=name, main_app=main_app))

    def add_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.HTTPHandler] = None,
        methods: t.List[str] = None,
        name: str = None,
        include_in_schema: bool = True,
        route: BaseRoute = None,
    ):
        """Register a new HTTP route in this router under given path.

        :param path: URL path.
        :param endpoint: HTTP endpoint.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param route: HTTP route.
        """
        try:
            main_app = self.main_app
        except AttributeError:
            main_app = None

        if path is not None and endpoint is not None:
            route = Route(
                path,
                endpoint=endpoint,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
                main_app=main_app,
            )
        elif route is not None:
            route.main_app = main_app  # type: ignore[assignment]
        else:
            raise ValueError("Either 'path' and 'endpoint' or 'route' variables are needed")

        self.routes.append(route)

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
    ):
        """Register a new websocket route in this router under given path.

        :param path: URL path.
        :param endpoint: Websocket function or endpoint.
        :param name: Websocket route name.
        :param route: Specific route class.
        """
        try:
            main_app = self.main_app
        except AttributeError:
            main_app = None

        if path is not None and endpoint is not None:
            route = WebSocketRoute(path, endpoint=endpoint, name=name, main_app=main_app)
        elif route is not None:
            route.main_app = main_app  # type: ignore[assignment]
        else:
            raise ValueError("Either 'path' and 'endpoint' or 'route' variables are needed")

        self.routes.append(route)

    def websocket_route(
        self, path: str, name: str = None
    ) -> t.Callable[[types.WebSocketHandler], types.WebSocketHandler]:
        """Decorator version for registering a new websocket route in this router under given path.

        :param path: URL path.
        :param name: Websocket route name.
        :return: Decorated route.
        """

        def decorator(func: types.WebSocketHandler) -> types.WebSocketHandler:
            self.add_websocket_route(path, func, name=name)
            return func

        return decorator

    def get_route_from_scope(self, scope, mounted=False) -> t.Tuple[t.Union[BaseRoute, types.App], t.Optional[t.Dict]]:
        partial = None

        for route in self.routes:
            if isinstance(route, Mount):
                path = scope.get("path", "")
                root_path = scope.pop("root_path", "")
                if not mounted:
                    scope["path"] = root_path + path

            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                scope.update(child_scope)

                if isinstance(route, Mount) and isinstance(route.app, Router):
                    if mounted:
                        scope["root_path"] = root_path + child_scope.get("root_path", "")
                    mount_route, mount_scope = route.app.get_route_from_scope(scope, mounted=True)
                    return mount_route, mount_scope

                return route, scope
            elif match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            scope.update(partial_scope)
            return partial, scope

        return NotFound(), None


class NotFound(types.AppClass):
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] == "websocket":
            websocket_close = websockets.Close()
            await websocket_close(scope, receive, send)
            return

        # If we're running inside a starlette application then raise an exception, so that the configurable exception
        # handler can deal with returning the response. For plain ASGI apps, just return the response.
        if "app" in scope:
            raise exceptions.HTTPException(status_code=HTTPStatus.NOT_FOUND)

        response = http.PlainTextResponse("Not Found", status_code=HTTPStatus.NOT_FOUND)
        await response(scope, receive, send)
