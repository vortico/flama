import asyncio
import inspect
import typing
from functools import wraps

import marshmallow
import starlette.routing
from starlette.concurrency import run_in_threadpool
from starlette.routing import Match, Mount
from starlette.types import ASGIApp, ASGIInstance, Receive, Scope, Send

from flama import http, websockets
from flama.components import Component
from flama.responses import APIResponse
from flama.types import Field, FieldLocation, HTTPMethod, OptBool, OptFloat, OptInt, OptStr
from flama.validation import get_output_schema

if typing.TYPE_CHECKING:
    from flama.resources import BaseResource

__all__ = ["Route", "WebSocketRoute", "Router"]


FieldsMap = typing.Dict[str, Field]
MethodsMap = typing.Dict[str, FieldsMap]

PATH_SCHEMA_MAPPING = {
    inspect.Signature.empty: lambda *args, **kwargs: None,
    int: marshmallow.fields.Integer,
    float: marshmallow.fields.Number,
    str: marshmallow.fields.String,
    bool: marshmallow.fields.Boolean,
    http.PathParam: marshmallow.fields.String,
}

QUERY_SCHEMA_MAPPING = {
    inspect.Signature.empty: lambda *args, **kwargs: None,
    int: marshmallow.fields.Integer,
    float: marshmallow.fields.Number,
    bool: marshmallow.fields.Boolean,
    str: marshmallow.fields.String,
    OptInt: marshmallow.fields.Integer,
    OptFloat: marshmallow.fields.Number,
    OptBool: marshmallow.fields.Boolean,
    OptStr: marshmallow.fields.String,
    http.QueryParam: marshmallow.fields.String,
}


class FieldsMixin:
    def _get_fields(
        self, router: "Router"
    ) -> typing.Tuple[MethodsMap, MethodsMap, typing.Dict[str, Field], typing.Dict[str, typing.Any]]:
        query_fields: MethodsMap = {}
        path_fields: MethodsMap = {}
        body_field: typing.Dict[str, Field] = {}
        output_field: typing.Dict[str, typing.Any] = {}

        if hasattr(self, "methods") and self.methods is not None:
            if inspect.isclass(self.endpoint):  # HTTP endpoint
                methods = [(m, getattr(self.endpoint, m.lower() if m != "HEAD" else "get")) for m in self.methods]
            else:  # HTTP function
                methods = [(m, self.endpoint) for m in self.methods] if self.methods else []
        else:  # Websocket
            methods = [("GET", self.endpoint)]

        for m, h in methods:
            query_fields[m], path_fields[m], body_field[m], output_field[m] = self._get_fields_from_handler(h, router)

        return query_fields, path_fields, body_field, output_field

    def _get_parameters_from_handler(
        self, handler: typing.Callable, router: "Router"
    ) -> typing.Dict[str, inspect.Parameter]:
        parameters = {}

        for name, parameter in inspect.signature(handler).parameters.items():
            for component in router.components:
                if component.can_handle_parameter(parameter):
                    parameters.update(self._get_parameters_from_handler(component.resolve, router))
                    break
            else:
                parameters[name] = parameter

        return parameters

    def _get_fields_from_handler(
        self, handler: typing.Callable, router: "Router"
    ) -> typing.Tuple[FieldsMap, FieldsMap, Field, typing.Any]:
        query_fields: FieldsMap = {}
        path_fields: FieldsMap = {}
        body_field: Field = None

        # Iterate over all params
        for name, param in self._get_parameters_from_handler(handler, router).items():
            if name in ("self", "cls"):
                continue

            # Matches as path param
            if name in self.param_convertors.keys():
                try:
                    schema = PATH_SCHEMA_MAPPING[param.annotation]
                except KeyError:
                    schema = marshmallow.fields.String

                path_fields[name] = Field(
                    name=name, location=FieldLocation.path, schema=schema(required=True), required=True
                )

            # Matches as query param
            elif param.annotation in QUERY_SCHEMA_MAPPING:
                if param.annotation in (OptInt, OptFloat, OptBool, OptStr) or param.default is not param.empty:
                    required = False
                    kwargs = {"missing": param.default if param.default is not param.empty else None}
                else:
                    required = True
                    kwargs = {"required": True}

                query_fields[name] = Field(
                    name=name,
                    location=FieldLocation.query,
                    schema=QUERY_SCHEMA_MAPPING[param.annotation](**kwargs),
                    required=required,
                )

            # Body params
            elif inspect.isclass(param.annotation) and issubclass(param.annotation, marshmallow.Schema):
                body_field = Field(name=name, location=FieldLocation.body, schema=param.annotation())

        output_field = inspect.signature(handler).return_annotation

        return query_fields, path_fields, body_field, output_field


class Route(starlette.routing.Route, FieldsMixin):
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
                    "request": http.Request(scope, receive),
                }

                injected_func = await app.injector.inject(endpoint, state)

                if asyncio.iscoroutinefunction(endpoint):
                    response = await injected_func()
                else:
                    response = await run_in_threadpool(injected_func)

                # Wrap response data with a proper response class
                if isinstance(response, (dict, list)):
                    response = APIResponse(content=response, schema=get_output_schema(endpoint))
                elif isinstance(response, str):
                    response = APIResponse(content=response)
                elif response is None:
                    response = APIResponse(content="")

                await response(receive, send)

            return awaitable

        return _app


class WebSocketRoute(starlette.routing.WebSocketRoute, FieldsMixin):
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
                    "websocket": websockets.WebSocket(scope, receive, send),
                }

                injected_func = await app.injector.inject(endpoint, state)

                kwargs = scope.get("kwargs", {})
                await injected_func(**kwargs)

            return awaitable

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

    def get_route_from_scope(self, scope) -> typing.Tuple[Route, typing.Optional[typing.Dict]]:
        partial = None

        for route in self.routes:
            if isinstance(route, Mount):
                path = scope.get("path", "")
                root_path = scope.pop("root_path", "")
                scope["path"] = root_path + path

            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                scope.update(child_scope)

                if isinstance(route, Mount):
                    route, mount_scope = route.app.get_route_from_scope(scope)
                    return route, mount_scope

                return route, scope
            elif match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            scope.update(partial_scope)
            return partial, scope

        return self.not_found, None
