import asyncio
import enum
import inspect
import typing
from dataclasses import dataclass
from functools import wraps

import starlette.routing
from starlette.responses import JSONResponse, Response
from starlette.routing import Match, Mount
from starlette.types import ASGIApp, ASGIInstance, Receive, Scope, Send

import marshmallow
from starlette_api import http

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


FieldsMap = typing.Dict[str, Field]
MethodsMap = typing.Dict[str, FieldsMap]


class FieldsMixin:
    def _get_fields(self) -> typing.Tuple[MethodsMap, MethodsMap, typing.Dict[str, Field]]:
        query_fields: MethodsMap = {}
        path_fields: MethodsMap = {}
        body_field: typing.Dict[str, Field] = {}

        if hasattr(self, "methods"):
            if inspect.isclass(self.endpoint):  # HTTP endpoint
                methods = [(m, getattr(self.endpoint, m.lower())) for m in self.methods] if self.methods else []
            else:  # HTTP function
                methods = [(self.methods[0], self.endpoint)]
        else:  # Websocket
            methods = [("GET", self.endpoint)]

        for method, handler in methods:
            query_fields[method], path_fields[method], body_field[method] = self._get_fields_from_handler(handler)

        return query_fields, path_fields, body_field

    def _get_fields_from_handler(self, handler: typing.Callable) -> typing.Tuple[FieldsMap, FieldsMap, Field]:
        query_fields: FieldsMap = {}
        path_fields: FieldsMap = {}
        body_field: Field = None

        # Iterate over all params
        parameters = inspect.signature(handler).parameters
        for name, param in parameters.items():
            if name in ("self", "cls"):
                continue

            # Matches as path param
            if name in self.param_convertors.keys():
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
    def __init__(self, path: str, endpoint: typing.Callable, *args, **kwargs):
        super().__init__(path, endpoint=endpoint, **kwargs)

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint):
            self.app = self.endpoint_wrapper(endpoint)

        self.query_fields, self.path_fields, self.body_field = self._get_fields()

    def endpoint_wrapper(self, endpoint: typing.Callable) -> ASGIApp:
        """
        Wraps a http function into ASGI application.
        """

        @wraps(endpoint)
        def _app(scope: Scope) -> ASGIInstance:
            async def awaitable(receive: Receive, send: Send) -> None:
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
                }

                injected_func = await app.injector.inject(endpoint, state)

                if asyncio.iscoroutinefunction(endpoint):
                    response = await injected_func()
                else:
                    response = injected_func()

                # Use output schema to validate and format data
                return_annotation = inspect.signature(endpoint).return_annotation
                if inspect.isclass(return_annotation) and issubclass(return_annotation, marshmallow.Schema):
                    response = return_annotation().dump(response)
                elif isinstance(return_annotation, marshmallow.Schema):
                    response = return_annotation.dump(response)

                # Wrap response data with a proper response class
                if isinstance(response, (dict, list)):
                    response = JSONResponse(response)
                elif isinstance(response, str):
                    response = Response(response)

                await response(receive, send)

            return awaitable

        return _app


class WebSocketRoute(starlette.routing.WebSocketRoute, FieldsMixin):
    def __init__(self, path: str, endpoint: typing.Callable, *args, **kwargs):
        super().__init__(path, endpoint=endpoint, **kwargs)

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint):
            self.app = self.endpoint_wrapper(endpoint)

        self.query_fields, self.path_fields, self.body_field = self._get_fields()

    def endpoint_wrapper(self, endpoint: typing.Callable) -> ASGIApp:
        """
        Wraps websocket function into ASGI application.
        """

        @wraps(endpoint)
        def _app(scope: Scope) -> ASGIInstance:
            async def awaitable(receive: Receive, send: Send) -> None:
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
                }

                injected_func = await app.injector.inject(endpoint, state)

                kwargs = scope.get("kwargs", {})
                await injected_func(**kwargs)

            return awaitable

        return _app


class Router(starlette.routing.Router):
    def add_route(
        self,
        path: str,
        endpoint: typing.Callable,
        methods: typing.List[str] = None,
        name: str = None,
        include_in_schema: bool = True,
    ):
        self.routes.append(
            Route(path, endpoint=endpoint, methods=methods, name=name, include_in_schema=include_in_schema)
        )

    def route(
        self, path: str, methods: typing.List[str] = None, name: str = None, include_in_schema: bool = True
    ) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_route(path, func, methods=methods, name=name, include_in_schema=include_in_schema)
            return func

        return decorator

    def add_websocket_route(self, path: str, endpoint: typing.Callable, name: str = None):
        self.routes.append(WebSocketRoute(path, endpoint=endpoint, name=name))

    def websocket_route(self, path: str, name: str = None) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_websocket_route(path, func, name=name)
            return func

        return decorator

    def get_route_from_scope(self, scope) -> typing.Tuple[Route, typing.Optional[typing.Dict]]:
        if "root_path" in scope:
            scope["path"] = scope["root_path"] + scope["path"]
            del scope["root_path"]

        partial = None

        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                scope.update(child_scope)

                if isinstance(route, Mount):
                    del scope["root_path"]
                    return route.app.get_route_from_scope(scope)

                return route, scope
            elif match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            scope.update(partial_scope)
            return partial, scope

        return self.not_found, None
