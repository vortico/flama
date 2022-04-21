import asyncio
import inspect
import logging
import typing
from functools import wraps

import starlette.routing
from starlette.concurrency import run_in_threadpool
from starlette.routing import Match
from starlette.types import ASGIApp, Receive, Scope, Send

from flama import http, websockets
from flama.components import Component, Components
from flama.responses import APIResponse, Response
from flama.schemas.routing import RouteParametersMixin
from flama.schemas.utils import is_schema_instance
from flama.schemas.validation import get_output_schema
from flama.types import HTTPMethod

if typing.TYPE_CHECKING:
    from flama.applications import Flama
    from flama.lifespan import Lifespan

__all__ = ["Mount", "Route", "Router", "WebSocketRoute"]

logger = logging.getLogger(__name__)


async def prepare_http_request(app: "Flama", handler: typing.Callable, state: typing.Dict[str, typing.Any]) -> Response:
    try:
        injected_func = await app.injector.inject(handler, state)

        if asyncio.iscoroutinefunction(handler):
            response = await injected_func()
        else:
            response = await run_in_threadpool(injected_func)

        # Wrap response data with a proper response class
        if is_schema_instance(response):
            response = APIResponse(content=response, schema=response.__class__)
        elif isinstance(response, (dict, list)):
            response = APIResponse(content=response, schema=get_output_schema(handler))
        elif isinstance(response, str):
            response = APIResponse(content=response)
        elif response is None:
            response = APIResponse(content="")
    except Exception:
        logger.exception("Error building response")
        raise

    return response


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
        self, path: str, endpoint: typing.Callable, main_app: typing.Optional["Flama"] = None, *args, **kwargs
    ):
        super().__init__(path, endpoint=endpoint, **kwargs)

        if main_app is not None:
            self.main_app = main_app

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint) or inspect.ismethod(endpoint):
            self.app = self.endpoint_wrapper(endpoint)

        if self.methods is None:
            self.methods = {m for m in HTTPMethod.__members__.keys() if hasattr(self, m.lower())}

    def endpoint_wrapper(self, endpoint: typing.Callable) -> ASGIApp:
        """
        Wraps a http function into ASGI application.
        """

        @wraps(endpoint)
        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
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
                "request": http.Request(scope, receive),
            }
            response = await prepare_http_request(app, endpoint, state)
            await response(scope, receive, send)

        return _app


class WebSocketRoute(BaseRoute, starlette.routing.WebSocketRoute):
    def __init__(self, path: str, endpoint: typing.Callable, main_app: "Flama" = None, *args, **kwargs):
        super().__init__(path, endpoint=endpoint, **kwargs)

        if main_app is not None:
            self.main_app = main_app

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint):
            self.app = self.endpoint_wrapper(endpoint)

    def endpoint_wrapper(self, endpoint: typing.Callable) -> ASGIApp:
        """
        Wraps websocket function into ASGI application.
        """

        @wraps(endpoint)
        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
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

            try:
                injected_func = await app.injector.inject(endpoint, state)

                kwargs = scope.get("kwargs", {})
                await injected_func(**kwargs)
            except Exception:
                logger.exception("Error building response")
                raise

        return _app


class Mount(BaseRoute, starlette.routing.Mount):
    def __init__(
        self,
        path: str,
        main_app: "Flama" = None,
        app: ASGIApp = None,
        routes: typing.Sequence[BaseRoute] = None,
        name: str = None,
    ):
        if app is None:
            app = Router(routes=routes)

        super().__init__(path, app, routes, name)

        if main_app is not None:
            self.main_app = main_app


class Router(starlette.routing.Router):
    def __init__(
        self,
        main_app: "Flama" = None,
        components: typing.Sequence["Component"] = None,
        routes: typing.Sequence[BaseRoute] = None,
        lifespan: typing.Optional["Lifespan"] = None,
        *args,
        **kwargs,
    ):
        self._components = Components([*(components or [])])
        super().__init__(routes=routes, lifespan=lifespan, *args, **kwargs)  # type: ignore[misc]
        self.lifespan: typing.Optional["Lifespan"]  # type: ignore[assignment]
        self.routes: typing.List[BaseRoute] = list(self.routes)  # type: ignore[assignment]

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
            [component for route in self.routes for component in getattr(route.app, "components", [])]
        )

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        try:
            main_app = self.main_app
        except AttributeError:
            main_app = None

        self.routes.append(Mount(path.rstrip("/"), app=app, name=name, main_app=main_app))

    def add_route(
        self,
        path: str,
        endpoint: typing.Callable,
        methods: typing.List[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ):
        try:
            main_app = self.main_app
        except AttributeError:
            main_app = None

        self.routes.append(
            Route(
                path,
                endpoint=endpoint,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
                main_app=main_app,
            )
        )

    def route(
        self, path: str, methods: typing.List[str] = None, name: str = None, include_in_schema: bool = True
    ) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_route(path, func, methods=methods, name=name, include_in_schema=include_in_schema)
            return func

        return decorator

    def add_websocket_route(self, path: str, endpoint: typing.Callable, name: str = None):
        try:
            main_app = self.main_app
        except AttributeError:
            main_app = None

        self.routes.append(WebSocketRoute(path, endpoint=endpoint, name=name, main_app=main_app))

    def websocket_route(self, path: str, name: str = None) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_websocket_route(path, func, name=name)
            return func

        return decorator

    def get_route_from_scope(self, scope, mounted=False) -> typing.Tuple[Route, typing.Optional[typing.Dict]]:
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

                if isinstance(route, Mount):
                    if mounted:
                        scope["root_path"] = root_path + child_scope.get("root_path", "")
                    route, mount_scope = route.app.get_route_from_scope(scope, mounted=True)
                    return route, mount_scope

                return route, scope
            elif match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            scope.update(partial_scope)
            return partial, scope

        return self.not_found, None
