from inspect import Parameter
from urllib.parse import parse_qsl

from flama import types
from flama.components import Component, Components

__all__ = [
    "MethodComponent",
    "URLComponent",
    "SchemeComponent",
    "HostComponent",
    "PortComponent",
    "PathComponent",
    "QueryStringComponent",
    "QueryParamsComponent",
    "QueryParamComponent",
    "HeadersComponent",
    "HeaderComponent",
    "BodyComponent",
    "ASGI_COMPONENTS",
]


class MethodComponent(Component):
    def resolve(self, scope: types.Scope) -> types.Method:
        return types.Method(scope["method"])


class URLComponent(Component):
    def resolve(self, scope: types.Scope) -> types.URL:
        return types.URL(scope=scope)


class SchemeComponent(Component):
    def resolve(self, scope: types.Scope) -> types.Scheme:
        return types.Scheme(scope["scheme"])


class HostComponent(Component):
    def resolve(self, scope: types.Scope) -> types.Host:
        return types.Host(scope["server"][0])


class PortComponent(Component):
    def resolve(self, scope: types.Scope) -> types.Port:
        return types.Port(scope["server"][1])


class PathComponent(Component):
    def resolve(self, scope: types.Scope) -> types.Path:
        return types.Path(scope.get("root_path", "") + scope["path"])


class QueryStringComponent(Component):
    def resolve(self, scope: types.Scope) -> types.QueryString:
        return types.QueryString(scope["query_string"].decode())


class QueryParamsComponent(Component):
    def resolve(self, scope: types.Scope) -> types.QueryParams:
        query_string = scope["query_string"].decode()
        return types.QueryParams(parse_qsl(query_string))


class QueryParamComponent(Component):
    def resolve(self, parameter: Parameter, query_params: types.QueryParams) -> types.QueryParam:
        name = parameter.name
        if name not in query_params:
            return None  # type: ignore[return-value]
        return types.QueryParam(query_params[name])


class HeadersComponent(Component):
    def resolve(self, scope: types.Scope) -> types.Headers:
        return types.Headers(scope=scope)


class HeaderComponent(Component):
    def resolve(self, parameter: Parameter, headers: types.Headers) -> types.Header:
        name = parameter.name.replace("_", "-")
        if name not in headers:
            return None  # type: ignore[return-value]
        return types.Header(headers[name])


class BodyComponent(Component):
    async def resolve(self, receive: types.Receive) -> types.Body:
        body = b""
        while True:
            message = await receive()
            if not message["type"] == "http.request":
                raise Exception(f"Unexpected ASGI message type '{message['type']}'.")
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        return types.Body(body)


ASGI_COMPONENTS = Components(
    [
        MethodComponent(),
        URLComponent(),
        SchemeComponent(),
        HostComponent(),
        PortComponent(),
        PathComponent(),
        QueryStringComponent(),
        QueryParamsComponent(),
        QueryParamComponent(),
        HeadersComponent(),
        HeaderComponent(),
        BodyComponent(),
    ]
)
