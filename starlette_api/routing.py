import asyncio
import enum
import inspect
import typing
from dataclasses import dataclass
from functools import wraps

import starlette.routing
from starlette.responses import JSONResponse, Response
from starlette.routing import Match
from starlette.types import ASGIApp, ASGIInstance, Receive, Scope, Send

import marshmallow
from starlette_api import http

MYPY = False
if MYPY:
    from starlette_api.applications import Starlette

__all__ = ["Route", "WebSocketRoute", "Router"]


class Location(enum.Enum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()


@dataclass
class Field:
    name: str
    location: Location
    schema: typing.Union[marshmallow.fields.Field, marshmallow.Schema]
    required: bool = False


class FieldsMixin:
    def _get_fields(
        self, handler: typing.Callable
    ) -> typing.Tuple[typing.Dict[str, Field], typing.Dict[str, Field], Field]:
        query_fields: typing.Dict[str, Field] = {}
        path_fields: typing.Dict[str, Field] = {}
        body_field: Field = None

        # Iterate over all params
        parameters = inspect.signature(handler).parameters
        for name, param in parameters.items():
            # Matches as path param
            if name in self.param_names:
                schema = {
                    param.empty: None,
                    int: marshmallow.fields.Integer(required=True),
                    float: marshmallow.fields.Number(required=True),
                    str: marshmallow.fields.String(required=True),
                }[param.annotation]
                path_fields[name] = Field(name=name, location=Location.path, schema=schema)

            # Matches as query param
            elif param.annotation in (param.empty, int, float, bool, str, http.QueryParam):
                if param.default is param.empty:
                    kwargs = {"required": True}
                else:
                    kwargs = {"missing": param.default}
                schema = {
                    param.empty: None,
                    int: marshmallow.fields.Integer(**kwargs),
                    float: marshmallow.fields.Number(**kwargs),
                    bool: marshmallow.fields.Boolean(**kwargs),
                    str: marshmallow.fields.String(**kwargs),
                    http.QueryParam: marshmallow.fields.String(**kwargs),
                }[param.annotation]
                query_fields[name] = Field(name=name, location=Location.query, schema=schema)

            # Body params
            elif inspect.isclass(param.annotation) and issubclass(param.annotation, marshmallow.Schema):
                body_field = Field(name=name, location=Location.body, schema=param.annotation())

        return query_fields, path_fields, body_field


class Route(starlette.routing.Route, FieldsMixin):
    def __init__(self, path: str, *, endpoint: typing.Callable, app: "Starlette", methods: typing.List[str] = None):
        super().__init__(path, endpoint=endpoint, methods=methods)

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint):
            self.app = self.endpoint_wrapper(endpoint, app)
        else:
            self.app.injector = app.injector
            self.app.app = app

        self.query_fields, self.path_fields, self.body_field = self._get_fields(endpoint)

    def endpoint_wrapper(self, endpoint: typing.Callable, app: "Starlette") -> ASGIApp:
        """
        Wraps a http function into ASGI application.
        """

        @wraps(endpoint)
        def _app(scope: Scope) -> ASGIInstance:
            async def awaitable(receive: Receive, send: Send) -> None:
                route, route_scope = app.router.get_route_from_scope(scope)

                state = {
                    "scope": scope,
                    "receive": receive,
                    "send": send,
                    "exc": None,
                    "app": None,
                    "path_params": route_scope["path_params"],
                    "route": route,
                }

                injected_func = await app.injector.inject(endpoint, state)

                if asyncio.iscoroutinefunction(endpoint):
                    response = await injected_func()
                else:
                    response = injected_func()

                return_annotation = inspect.signature(endpoint).return_annotation
                if issubclass(return_annotation, marshmallow.Schema):
                    response = return_annotation().dump(response)

                if isinstance(response, (dict, list)):
                    response = JSONResponse(response)
                elif isinstance(response, str):
                    response = Response(response)

                await response(receive, send)

            return awaitable

        return _app


class WebSocketRoute(starlette.routing.WebSocketRoute, FieldsMixin):
    def __init__(self, path: str, *, endpoint: typing.Callable, app: "Starlette"):
        super().__init__(path, endpoint=endpoint)

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint):
            self.app = self.endpoint_wrapper(endpoint, app)
        else:
            self.app.injector = app.injector
            self.app.app = app

        self.query_fields, self.path_fields, self.body_field = self._get_fields(endpoint)

    def endpoint_wrapper(self, endpoint: typing.Callable, app: "Starlette") -> ASGIApp:
        """
        Wraps websocket function into ASGI application.
        """

        @wraps(endpoint)
        def _app(scope: Scope) -> ASGIInstance:
            async def awaitable(receive: Receive, send: Send) -> None:
                route, route_scope = app.router.get_route_from_scope(scope)

                state = {
                    "scope": scope,
                    "receive": receive,
                    "send": send,
                    "exc": None,
                    "app": app,
                    "path_params": route_scope["path_params"],
                    "route": route,
                }

                injected_func = await app.injector.inject(endpoint, state)

                kwargs = scope.get("kwargs", {})
                await injected_func(**kwargs)

            return awaitable

        return _app


class Router(starlette.routing.Router):
    def add_route(self, path: str, endpoint: typing.Callable, app: "Starlette", methods: typing.List[str] = None):
        self.routes.append(Route(path, endpoint=endpoint, methods=methods, app=app))

    def route(self, path: str, app: "Starlette", methods: typing.List[str] = None) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_route(path, func, methods=methods, app=app)
            return func

        return decorator

    def add_websocket_route(self, path: str, endpoint: typing.Callable, app: "Starlette"):
        self.routes.append(WebSocketRoute(path, endpoint=endpoint, app=app))

    def websocket_route(self, path: str, app: "Starlette") -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_websocket_route(path, func, app=app)
            return func

        return decorator

    def get_route_from_scope(self, scope) -> typing.Tuple[Route, typing.Optional[typing.Dict]]:
        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match != Match.NONE:
                return route, child_scope

        return self.not_found, None
