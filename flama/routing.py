import asyncio
import inspect
import logging
import typing
from functools import wraps

import starlette.routing
from starlette.concurrency import run_in_threadpool
from starlette.routing import Match, Mount
from starlette.types import ASGIApp, Receive, Scope, Send

from flama import http, websockets
from flama.components import Component
from flama.responses import APIResponse, Response
from flama.schemas.routing import RouteFieldsMixin
from flama.schemas.utils import is_schema_instance
from flama.schemas.validation import get_output_schema
from flama.types import HTTPMethod

if typing.TYPE_CHECKING:
    from flama.applications import Flama
    from flama.resources import BaseResource

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


class BaseRoute(starlette.routing.BaseRoute, RouteFieldsMixin):
    ...


class Route(starlette.routing.Route, BaseRoute):
    def __init__(self, path: str, endpoint: typing.Callable, router: "Router", *args, **kwargs):
        super().__init__(path, endpoint=endpoint, **kwargs)

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint) or inspect.ismethod(endpoint):
            self.app = self.endpoint_wrapper(endpoint)

        if self.methods is None:
            self.methods = [m for m in HTTPMethod.__members__.keys() if hasattr(self, m.lower())]

        self.query_fields, self.path_fields, self.body_field, self.output_field = self._get_fields(router)

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


class WebSocketRoute(starlette.routing.WebSocketRoute, BaseRoute):
    def __init__(self, path: str, endpoint: typing.Callable, router: "Router", *args, **kwargs):
        super().__init__(path, endpoint=endpoint, **kwargs)

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint):
            self.app = self.endpoint_wrapper(endpoint)

        self.query_fields, self.path_fields, self.body_field, self.output_field = self._get_fields(router)

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


class Router(starlette.routing.Router):
    def __init__(self, components: typing.Optional[typing.List[Component]] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if components is None:
            components = []

        self.components = components

    def add_route(
        self,
        path: str,
        endpoint: typing.Callable,
        methods: typing.List[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ):
        self.routes.append(
            Route(path, endpoint=endpoint, methods=methods, name=name, include_in_schema=include_in_schema, router=self)
        )

    def add_websocket_route(self, path: str, endpoint: typing.Callable, name: str = None):
        self.routes.append(WebSocketRoute(path, endpoint=endpoint, name=name, router=self))

    def add_resource(self, path: str, resource: "BaseResource"):
        # Handle class or instance objects
        if inspect.isclass(resource):  # noqa
            resource = resource()

        for name, route in resource.routes.items():
            route_path = path + resource._meta.name + route._meta.path
            route_func = getattr(resource, name)
            name = route._meta.name if route._meta.name is not None else f"{resource._meta.name}-{route.__name__}"
            self.add_route(route_path, route_func, route._meta.methods, name, **route._meta.kwargs)

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        if isinstance(app, Router):
            app.components = self.components

        path = path.rstrip("/")
        route = Mount(path, app=app, name=name)
        self.routes.append(route)

    def route(
        self, path: str, methods: typing.List[str] = None, name: str = None, include_in_schema: bool = True
    ) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_route(path, func, methods=methods, name=name, include_in_schema=include_in_schema)
            return func

        return decorator

    def websocket_route(self, path: str, name: str = None) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_websocket_route(path, func, name=name)
            return func

        return decorator

    def resource(self, path: str) -> typing.Callable:
        def decorator(resource: "BaseResource") -> "BaseResource":
            self.add_resource(path, resource=resource)
            return resource

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
