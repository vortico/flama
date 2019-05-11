from inspect import Parameter
from urllib.parse import parse_qsl

from flama.components import Component
from flama.types import asgi, http

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
    def resolve(self, scope: asgi.Scope) -> http.Method:
        return http.Method(scope["method"])


class URLComponent(Component):
    def resolve(self, scope: asgi.Scope) -> http.URL:
        return http.URL(scope=scope)


class SchemeComponent(Component):
    def resolve(self, scope: asgi.Scope) -> http.Scheme:
        return http.Scheme(scope["scheme"])


class HostComponent(Component):
    def resolve(self, scope: asgi.Scope) -> http.Host:
        return http.Host(scope["server"][0])


class PortComponent(Component):
    def resolve(self, scope: asgi.Scope) -> http.Port:
        return http.Port(scope["server"][1])


class PathComponent(Component):
    def resolve(self, scope: asgi.Scope) -> http.Path:
        return http.Path(scope.get("root_path", "") + scope["path"])


class QueryStringComponent(Component):
    def resolve(self, scope: asgi.Scope) -> http.QueryString:
        return http.QueryString(scope["query_string"].decode())


class QueryParamsComponent(Component):
    def resolve(self, scope: asgi.Scope) -> http.QueryParams:
        query_string = scope["query_string"].decode()
        return http.QueryParams(parse_qsl(query_string))


class QueryParamComponent(Component):
    def resolve(self, parameter: Parameter, query_params: http.QueryParams) -> http.QueryParam:
        name = parameter.name
        if name not in query_params:
            return None
        return http.QueryParam(query_params[name])


class HeadersComponent(Component):
    def resolve(self, scope: asgi.Scope) -> http.Headers:
        return http.Headers(scope=scope)


class HeaderComponent(Component):
    def resolve(self, parameter: Parameter, headers: http.Headers) -> http.Header:
        name = parameter.name.replace("_", "-")
        if name not in headers:
            return None
        return http.Header(headers[name])


class BodyComponent(Component):
    async def resolve(self, receive: asgi.Receive) -> http.Body:
        body = b""
        while True:
            message = await receive()
            if not message["type"] == "http.request":
                raise Exception(f"Unexpected ASGI message type '{message['type']}'.")
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        return http.Body(body)


ASGI_COMPONENTS = (
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
)
