import asyncio
import inspect
import re
import typing
from functools import wraps

import starlette.routing
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, ASGIInstance, Receive, Scope, Send

from starlette_api import http
from starlette_api.schema import document, types, validators

MYPY = False
if MYPY:
    from starlette_api.applications import Starlette

__all__ = ["Route", "WebSocketRoute", "APIRoute", "Router"]


def asgi_from_http(func: typing.Callable, app: "Starlette") -> ASGIApp:
    """
    Wraps a http function into ASGI application.
    """

    @wraps(func)
    def _app(scope: Scope) -> ASGIInstance:
        async def awaitable(receive: Receive, send: Send) -> None:
            path, path_params = app.router.get_route_from_scope(scope)

            state = {
                "scope": scope,
                "receive": receive,
                "send": send,
                "exc": None,
                "app": None,
                "path_params": path_params,
                "route": path,
            }

            injected_func = await app.injector.inject(func, state)

            if asyncio.iscoroutinefunction(func):
                response = await injected_func()
            else:
                response = injected_func()

            if isinstance(response, (dict, list, types.Type)):
                response = JSONResponse(response)
            elif isinstance(response, str):
                response = Response(response)

            await response(receive, send)

        return awaitable

    return _app


def asgi_from_websocket(func: typing.Callable, app: "Starlette") -> ASGIApp:
    """
    Wraps websocket function into ASGI application.
    """

    @wraps(func)
    def _app(scope: Scope) -> ASGIInstance:
        async def awaitable(receive: Receive, send: Send) -> None:
            state = {
                "scope": scope,
                "receive": receive,
                "send": send,
                "exc": None,
                "app": app,
                "path_params": None,
                "route": app.router.get_route_from_scope(scope),
            }

            injected_func = await app.injector.inject(func, state)

            kwargs = scope.get("kwargs", {})
            await injected_func(**kwargs)

        return awaitable

    return _app


class Route(starlette.routing.Route):
    def __init__(self, path: str, *, endpoint: typing.Callable, app: "Starlette", methods: typing.List[str] = None):
        super().__init__(path, endpoint=endpoint, methods=methods)

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint):
            self.app = asgi_from_http(endpoint, app)
        else:
            self.app.injector = app.injector
            self.app.app = app


class WebSocketRoute(starlette.routing.WebSocketRoute):
    def __init__(self, path: str, *, endpoint: typing.Callable, app: "Starlette"):
        super().__init__(path, endpoint=endpoint)

        # Replace function with another wrapper that uses the injector
        if inspect.isfunction(endpoint):
            self.app = asgi_from_websocket(endpoint, app)
        else:
            self.app.injector = app.injector
            self.app.app = app


class APIRoute(Route):
    def __init__(
        self,
        path: str,
        endpoint: typing.Callable,
        app: "Starlette",
        methods: typing.List[str] = None,
        name=None,
        documented=True,
        standalone=False,
    ):
        super().__init__(path, endpoint=endpoint, methods=methods, app=app)
        self.name = name or self.name
        self.documented = documented
        self.standalone = standalone

        if len(self.methods) == 1:
            self.link = self.generate_link(path, self.methods[0], app, self.name)
            self.section = None
        else:
            self.link = None
            self.section = self.generate_section(path, self.methods, app, self.name)

    def generate_section(self, path, methods, app, name):
        content = self.generate_content(path, methods, app)
        return document.Section(name=name, content=content)

    def generate_content(self, path, methods, app):
        content = []
        for method in methods:
            if inspect.isclass(app):
                link = self.generate_link(path, method, getattr(app, method), method)
            else:
                link = self.generate_link(path, method, app, method)

            content.append(link)

        return content

    def generate_link(self, url, method, handler, name):
        fields = self.generate_fields(url, method, handler)
        response = self.generate_response(handler)
        encoding = None
        if any([f.location == "body" for f in fields]):
            encoding = "application/json"
        return document.Link(
            url=url,
            method=method,
            name=name,
            encoding=encoding,
            fields=fields,
            response=response,
            description=handler.__doc__,
        )

    def generate_fields(self, url, method, handler):
        fields = []
        path_names = [item.strip("{}").lstrip("+") for item in re.findall("{[^}]*}", url)]
        parameters = inspect.signature(handler).parameters
        for name, param in parameters.items():
            if name in path_names:
                schema = {
                    param.empty: None,
                    int: validators.Integer(),
                    float: validators.Number(),
                    str: validators.String(),
                }[param.annotation]
                field = document.Field(name=name, location="path", schema=schema)
                fields.append(field)

            elif param.annotation in (param.empty, int, float, bool, str, http.QueryParam):
                if param.default is param.empty:
                    kwargs = {}
                elif param.default is None:
                    kwargs = {"default": None, "allow_null": True}
                else:
                    kwargs = {"default": param.default}
                schema = {
                    param.empty: None,
                    int: validators.Integer(**kwargs),
                    float: validators.Number(**kwargs),
                    bool: validators.Boolean(**kwargs),
                    str: validators.String(**kwargs),
                    http.QueryParam: validators.String(**kwargs),
                }[param.annotation]
                field = document.Field(name=name, location="query", schema=schema)
                fields.append(field)

            elif issubclass(param.annotation, types.Type):
                if method in ("GET", "DELETE"):
                    for name, validator in param.annotation.validator.properties.items():
                        field = document.Field(name=name, location="query", schema=validator)
                        fields.append(field)
                else:
                    field = document.Field(name=name, location="body", schema=param.annotation.validator)
                    fields.append(field)

        return fields

    def generate_response(self, handler):
        annotation = inspect.signature(handler).return_annotation
        annotation = self.coerce_generics(annotation)

        if not (issubclass(annotation, types.Type) or isinstance(annotation, validators.Validator)):
            return None

        return document.Response(encoding="application/json", status_code=200, schema=annotation)

    def coerce_generics(self, annotation):
        if (
            isinstance(annotation, type)
            and issubclass(annotation, typing.List)
            and getattr(annotation, "__args__", None)
            and issubclass(annotation.__args__[0], types.Type)
        ):
            return validators.Array(items=annotation.__args__[0])
        return annotation


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

    def add_api_route(self, path: str, endpoint: typing.Callable, app: "Starlette", methods: typing.List[str] = None):
        self.routes.append(APIRoute(path, endpoint=endpoint, methods=methods, app=app))

    def api_route(self, path: str, app: "Starlette", methods: typing.List[str] = None) -> typing.Callable:
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_api_route(path, func, methods=methods, app=app)
            return func

        return decorator

    def get_route_from_scope(self, scope) -> typing.Tuple[Route, typing.Optional[typing.Dict]]:
        for route in self.routes:
            matched, child_scope = route.matches(scope)
            if matched:
                return route, child_scope["path_params"]

        return self.not_found, None
