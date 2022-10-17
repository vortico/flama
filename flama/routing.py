import inspect
import logging
import typing as t
from functools import wraps

import starlette.routing
from starlette.routing import Match

from flama import concurrency, http, websockets
from flama.components import Component, Components
from flama.endpoints import HTTPEndpoint, WebSocketEndpoint
from flama.exceptions import HTTPException
from flama.responses import APIResponse, PlainTextResponse
from flama.schemas.routing import RouteParametersMixin
from flama.schemas.validation import get_output_schema
from flama.types import HTTPMethod
from flama.websockets import WebSocketClose

if t.TYPE_CHECKING:
    from flama import asgi
    from flama.applications import Flama
    from flama.lifespan import Lifespan

__all__ = ["Mount", "Route", "Router", "WebSocketRoute"]

logger = logging.getLogger(__name__)


class BaseRoute(RouteParametersMixin, starlette.routing.BaseRoute):
    @property
    def main_app(self) -> "Flama":
        try:
            return self._main_app
        except AttributeError:
            raise AttributeError(f"{self.__class__.__name__} is not initialized")

    @main_app.setter
    def main_app(self, app: "Flama"):
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
    def main_app(self):
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
        self, path: str, endpoint: t.Union[t.Callable, HTTPEndpoint], main_app: t.Optional["Flama"] = None, **kwargs
    ):
        """A route definition of a http endpoint.

        :param path: URL path.
        :param endpoint: HTTP endpoint or function.
        :param main_app: Flama app.
        """
        super().__init__(path, endpoint=endpoint, **kwargs)

        if main_app is not None:
            self.main_app = main_app

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint) or inspect.ismethod(endpoint):
            self.app = self._function_wrapper(endpoint)  # type: ignore[assignment]
        else:
            self.app = self._endpoint_wrapper(endpoint)  # type: ignore[assignment]

        if self.methods is None:
            self.methods = {m for m in HTTPMethod.__members__.keys() if hasattr(self.endpoint, m.lower())}

    def _build_api_response(self, handler: t.Callable, response: "http.Response") -> "http.Response":
        """Build an API response given a handler and the current response.

        It infers the output schema from the handler signature or just wraps the response in a APIResponse object.

        :param handler: The handler in charge of the request.
        :param response: The current response.
        :return: An API response.
        """
        if isinstance(response, (dict, list)):
            response = APIResponse(content=response, schema=get_output_schema(handler))
        elif isinstance(response, str):
            response = APIResponse(content=response)
        elif response is None:
            response = APIResponse(content="")

        return response

    def _function_wrapper(self, handler: t.Callable) -> "asgi.App":
        """Wraps an HTTP function into ASGI application.

        :param handler: HTTP function.
        :return: ASGI application.
        """

        @wraps(handler)
        async def _app(scope: "asgi.Scope", receive: "asgi.Receive", send: "asgi.Send") -> None:
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
                injected_func = await app.injector.inject(handler, state)
                response = await concurrency.run(injected_func)
                response = self._build_api_response(handler, response)
            except Exception:
                logger.exception("Error performing request")
                raise

            await response(scope, receive, send)

        return _app

    def _endpoint_wrapper(self, endpoint_class: t.Type[HTTPEndpoint]) -> "asgi.App":
        """Wraps an HTTP endpoint into ASGI application.

        :param endpoint_class: HTTP endpoint.
        :return: ASGI application.
        """

        @wraps(endpoint_class)
        async def _app(scope: "asgi.Scope", receive: "asgi.Receive", send: "asgi.Send") -> None:
            endpoint = endpoint_class(scope, receive, send)

            response = await endpoint
            response = self._build_api_response(endpoint.handler, response)

            await response(scope, receive, send)

        return _app


class WebSocketRoute(BaseRoute, starlette.routing.WebSocketRoute):
    def __init__(self, path: str, endpoint: t.Union[t.Callable, WebSocketEndpoint], main_app: "Flama" = None, **kwargs):
        """A route definition of a websocket endpoint.

        :param path: URL path.
        :param endpoint: Websocket endpoint or function.
        :param main_app: Flama app.
        """
        super().__init__(path, endpoint=endpoint, **kwargs)

        if main_app is not None:
            self.main_app = main_app

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint) or inspect.ismethod(endpoint):
            self.app = self._function_wrapper(endpoint)  # type: ignore[assignment]
        else:
            self.app = self._endpoint_wrapper(endpoint)  # type: ignore[assignment]

    def _function_wrapper(self, handler: t.Callable) -> "asgi.App":
        """Wraps a websocket function into ASGI application.

        :param handler: Websocket function.
        :return: ASGI application.
        """

        @wraps(handler)
        async def _app(scope: "asgi.Scope", receive: "asgi.Receive", send: "asgi.Send") -> None:
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
            }

            injected_func = await app.injector.inject(handler, state)
            await injected_func(**scope.get("kwargs", {}))

        return _app

    def _endpoint_wrapper(self, endpoint_class: t.Type[WebSocketEndpoint]) -> "asgi.App":
        """Wraps a Websocket endpoint into ASGI application.

        :param endpoint_class: Websocket endpoint.
        :return: ASGI application.
        """

        @wraps(endpoint_class)
        async def _app(scope: "asgi.Scope", receive: "asgi.Receive", send: "asgi.Send") -> None:
            await endpoint_class(scope, receive, send)

        return _app


class Mount(BaseRoute, starlette.routing.Mount):
    def __init__(
        self,
        path: str,
        main_app: "Flama" = None,
        app: "asgi.App" = None,
        routes: t.Sequence[BaseRoute] = None,
        components: t.Sequence[Component] = None,
        name: str = None,
    ):
        if app is None:
            app = Router(routes=routes, components=components)  # type: ignore[assignment]

        super().__init__(path, app, routes, name)

        if main_app is not None:
            self.main_app = main_app

    @property
    def routes(self) -> t.List[BaseRoute]:  # type: ignore[override]
        return getattr(self.app, "routes", [])


class Router(starlette.routing.Router):
    def __init__(
        self,
        main_app: "Flama" = None,
        components: t.Sequence["Component"] = None,
        routes: t.Sequence[BaseRoute] = None,
        lifespan: t.Optional["Lifespan"] = None,
        *args,
        **kwargs,
    ):
        self._components = Components([*(components or [])])
        super().__init__(routes=routes, lifespan=lifespan, *args, **kwargs)  # type: ignore[misc]
        self.lifespan: t.Optional["Lifespan"]  # type: ignore[assignment]
        self.routes: t.List[BaseRoute] = list(self.routes)  # type: ignore[assignment]

        if main_app is not None:
            self.main_app = main_app

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
        return self._components + Components(
            [
                component
                for route in self.routes
                if hasattr(route, "app") and hasattr(route.app, "components")  # type: ignore[attr-defined]
                for component in getattr(route.app, "components", [])  # type: ignore[attr-defined]
            ]
        )

    def add_component(self, component: Component):
        self._components.append(component)

    def mount(self, path: str, app: "asgi.App", name: str = None) -> None:
        try:
            main_app = self.main_app
        except AttributeError:
            main_app = None

        self.routes.append(Mount(path.rstrip("/"), app=app, name=name, main_app=main_app))

    def add_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[t.Callable] = None,
        methods: t.List[str] = None,
        name: str = None,
        include_in_schema: bool = True,
        route: BaseRoute = None,
    ):
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
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_route(path, func, methods=methods, name=name, include_in_schema=include_in_schema)
            return func

        return decorator

    def add_websocket_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[t.Callable] = None,
        name: str = None,
        route: t.Optional[WebSocketRoute] = None,
    ):
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

    def websocket_route(self, path: str, name: str = None) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_websocket_route(path, func, name=name)
            return func

        return decorator

    async def not_found(self, scope: "asgi.Scope", receive: "asgi.Receive", send: "asgi.Send") -> None:
        if scope["type"] == "websocket":
            websocket_close = WebSocketClose()
            await websocket_close(scope, receive, send)
            return

        # If we're running inside a starlette application then raise an exception, so that the configurable exception
        # handler can deal with returning the response. For plain ASGI apps, just return the response.
        if "app" in scope:
            raise HTTPException(status_code=404)

        response = PlainTextResponse("Not Found", status_code=404)
        await response(scope, receive, send)

    def get_route_from_scope(self, scope, mounted=False) -> t.Tuple[t.Union[BaseRoute, "asgi.App"], t.Optional[t.Dict]]:
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

        return self.not_found, None
