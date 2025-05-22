import inspect
import logging
import typing as t

from flama import compat, concurrency, endpoints, exceptions, http, schemas, types
from flama.routing.routes.base import BaseEndpointWrapper, BaseRoute

if t.TYPE_CHECKING:
    from flama import Flama

__all__ = ["Route"]

logger = logging.getLogger(__name__)


class BaseHTTPEndpointWrapper(BaseEndpointWrapper):
    def __init__(self, handler: types.Handler, *, pagination: t.Optional[types.Pagination] = None):
        super().__init__(handler, pagination=pagination)

        try:
            self.schema = schemas.Schema.from_type(inspect.signature(self.handler).return_annotation).unique_schema
        except Exception:
            self.schema = None

    def _build_api_response(self, response: t.Union[http.Response, None]) -> http.Response:
        """Build an API response given a handler and the current response.

        It infers the output schema from the handler signature or just wraps the response in a APIResponse object.

        :param response: The current response.
        :return: An API response.
        """
        if isinstance(response, (dict, list)):
            response = http.APIResponse(content=response, schema=self.schema)
        elif isinstance(response, (str, bytes)):
            response = http.APIResponse(content=response)
        elif response is None:
            response = http.APIResponse(content="")

        return response


class HTTPFunctionWrapper(BaseHTTPEndpointWrapper):
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        app: Flama = scope["app"]
        scope["path"] = scope.get("root_path", "").rstrip("/") + scope["path"]
        scope["root_path"] = ""
        route, route_scope = app.router.resolve_route(scope)
        context = {
            "scope": route_scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "route": route,
            "request": http.Request(route_scope, receive=receive),
        }

        injected_func = await app.injector.inject(self.handler, context)
        response = await concurrency.run(injected_func)
        response = self._build_api_response(response)

        await response(route_scope, receive, send)


class HTTPEndpointWrapper(BaseHTTPEndpointWrapper):
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        response = await self.handler(scope, receive, send)
        response = self._build_api_response(response)

        await response(scope, receive, send)


class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: types.HTTPHandler,
        *,
        methods: t.Optional[t.Union[set[str], t.Sequence[str]]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        pagination: t.Optional[types.Pagination] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> None:
        """A route definition of a http endpoint.

        :param path: URL path.
        :param endpoint: HTTP endpoint or function.
        :param methods: List of valid HTTP methods.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param pagination: Apply a pagination technique.
        :param tags: Route tags.
        """
        if not (self.is_endpoint(endpoint) or (not inspect.isclass(endpoint) and callable(endpoint))):
            raise exceptions.ApplicationError("Endpoint must be a callable or an HTTPEndpoint subclass")

        if self.is_endpoint(endpoint):
            self.methods = endpoint.allowed_methods() if methods is None else set(methods)
        else:
            self.methods = {"GET"} if methods is None else set(methods)

        if "GET" in self.methods:
            self.methods.add("HEAD")

        name = endpoint.__name__ if name is None else name
        wrapper = HTTPEndpointWrapper if inspect.isclass(endpoint) else HTTPFunctionWrapper

        super().__init__(
            path, wrapper(endpoint, pagination=pagination), name=name, include_in_schema=include_in_schema, tags=tags
        )

        self.app: BaseEndpointWrapper

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] == "http":
            await self.handle(types.Scope({**scope, **self.route_scope(scope)}), receive, send)

    def __hash__(self) -> int:
        return hash((self.app, self.path, self.name, tuple(self.methods)))

    def __eq__(self, other: t.Any) -> bool:
        return (
            isinstance(other, Route)
            and self.path == other.path
            and self.app == other.app
            and self.name == other.name
            and self.methods == other.methods
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r}, name={self.name!r}, methods={sorted(self.methods)!r})"

    @staticmethod
    def is_endpoint(
        x: t.Union[t.Callable, type[endpoints.HTTPEndpoint]],
    ) -> compat.TypeGuard[type[endpoints.HTTPEndpoint]]:  # PORT: Replace compat when stop supporting 3.9
        return inspect.isclass(x) and issubclass(x, endpoints.HTTPEndpoint)

    def endpoint_handlers(self) -> dict[str, t.Callable]:
        """Return a mapping of all possible endpoints of this route.

        Useful to identify all endpoints by HTTP methods.

        :return: Mapping of all endpoints.
        """
        if self.is_endpoint(self.endpoint):
            return {
                method: handler
                for method, handler in self.endpoint.allowed_handlers().items()
                if method in self.methods
            }

        return {method: self.endpoint for method in self.methods}

    def match(self, scope: types.Scope) -> BaseRoute.Match:
        """Check if this route matches with given scope.

        :param scope: ASGI scope.
        :return: Match.
        """
        if scope["type"] != "http":
            return self.Match.none

        m = super().match(scope)
        if m == self.Match.none:
            return m

        return self.Match.full if scope["method"] in self.methods else self.Match.partial
