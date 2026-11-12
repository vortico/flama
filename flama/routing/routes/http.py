import inspect
import logging
import typing as t

from flama import _concurrency, endpoints, exceptions, http, types
from flama.context import Context
from flama.http.responses.api import APIResponse
from flama.injection.resolver import Return
from flama.routing.routes._base import BaseEndpointWrapper, BaseRoute, RouteTableParams, ScopeType
from flama.schemas.data_structures import Parameter
from flama.types.http import Method

__all__ = ["Route"]

logger = logging.getLogger(__name__)


class BaseHTTPEndpointWrapper(BaseEndpointWrapper):
    def _output_schema(self, handler: t.Callable, signature: inspect.Signature) -> t.Any:
        """The schema a handler's output is serialised with, read from its return annotation.

        A handler returns a schema, a response, or nothing, or leaves its return type unannotated.

        :param handler: Handler.
        :param signature: Handler signature.
        :return: The schema, or None when the return annotation names none.
        :raises ApplicationError: If the return annotation is none of the supported forms.
        """
        output = Parameter.build("response", Return.from_return_annotation(signature.return_annotation))
        if output.schema is None:
            raise exceptions.ApplicationError(
                f"Route '{getattr(handler, '__qualname__', handler)}' returns "
                f"'{inspect.formatannotation(signature.return_annotation)}', but a route returns a schema, a "
                "response, or None, or has no return annotation"
            )

        return output.schema.unique_schema if output.schema.schema is not None else None

    def _build_api_response(self, response: object, schema: t.Any) -> http.Response:
        """Build an API response given a handler and the current response.

        Data is serialised with the handler's output schema, and so is an API response built without a schema.

        :param response: The current response.
        :param schema: The handler's output schema.
        :return: An API response.
        :raises SerializationError: If the handler returned neither a response, a mapping, a list nor None.
        """
        if isinstance(response, APIResponse) and response.schema is None:
            response.schema = schema
        elif isinstance(response, dict | list):
            response = APIResponse(response, schema=schema)
        elif response is None:
            response = APIResponse("")
        elif not isinstance(response, http.Response):
            raise exceptions.SerializationError(
                detail=f"Route returned a '{type(response).__name__}', but a route returns a response, a mapping, a "
                "list, or None"
            )

        return response


class HTTPFunctionWrapper(BaseHTTPEndpointWrapper):
    def __init__(
        self,
        handler: types.HTTPHandler,
        /,
        *,
        signature: inspect.Signature | None = None,
        pagination: types.Pagination | None = None,
    ):
        """Wraps an HTTP function into ASGI application.

        :param handler: Function.
        :param signature: Handler signature.
        :param pagination: Apply a pagination technique.
        """
        super().__init__(handler, signature=signature, pagination=pagination)

        self.schema = self._output_schema(self.handler, signature) if signature else None

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        app: types.App = scope["app"]
        scope["path"] = scope.get("root_path", "").rstrip("/") + scope["path"]
        scope["root_path"] = ""
        route, route_scope = app.router.resolve_route(scope)
        context = Context(
            scope=route_scope,
            receive=receive,
            send=send,
            exc=None,
            app=app,
            route=route,
            request=http.Request(route_scope, receive=receive),
        )

        try:
            injected_func = await app.injector.inject(self.handler, context)
            response = await _concurrency.run(injected_func)
            response = self._build_api_response(response, self.schema)

            await response(route_scope, receive, send)
        finally:
            await context.request.close()


class HTTPEndpointWrapper(BaseHTTPEndpointWrapper):
    handler: type[endpoints.HTTPEndpoint]

    def __init__(
        self,
        handler: types.Handler,
        /,
        *,
        signature: inspect.Signature | None = None,
        pagination: types.Pagination | None = None,
    ):
        """Wraps an HTTP endpoint into ASGI application.

        :param handler: Endpoint.
        :param signature: Endpoint signature.
        :param pagination: Apply a pagination technique.
        """
        super().__init__(handler, signature=signature, pagination=pagination)

        # Each method has its own handler, and so its own output schema. A JSON-RPC method's result is always sent
        # within a JSON-RPC response, so its annotation describes no HTTP response.
        self.schemas = (
            {
                method: self._output_schema(method_handler, inspect.signature(method_handler))
                for method, method_handler in self.handler.allowed_handlers().items()
            }
            if issubclass(self.handler, endpoints.HTTPEndpoint)
            else {}
        )

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        endpoint = self.handler(scope, receive, send)

        try:
            response = self._build_api_response(await endpoint, self.schemas.get(scope["method"]))

            await response(scope, receive, send)
        finally:
            await endpoint.state.request.close()


class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: types.HTTPHandler | BaseHTTPEndpointWrapper,
        *,
        methods: t.Sequence[Method] | None = None,
        name: str | None = None,
        include_in_schema: bool = True,
        pagination: types.Pagination | None = None,
        tags: dict[str, t.Any] | None = None,
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

        name = getattr(endpoint, "__name__", "") if name is None else name
        wrapped_endpoint = (
            endpoint
            if isinstance(endpoint, BaseHTTPEndpointWrapper)
            else HTTPEndpointWrapper(endpoint, signature=inspect.signature(endpoint), pagination=pagination)
            if inspect.isclass(endpoint)
            else HTTPFunctionWrapper(endpoint, signature=inspect.signature(endpoint), pagination=pagination)
        )

        super().__init__(path, wrapped_endpoint, name=name, include_in_schema=include_in_schema, tags=tags)

        self.app: BaseHTTPEndpointWrapper

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
    def is_endpoint(x: t.Callable | type[endpoints.HTTPEndpoint]) -> t.TypeGuard[type[endpoints.HTTPEndpoint]]:
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

    @property
    def _route_table_params(self) -> RouteTableParams:
        return RouteTableParams(scope_type=ScopeType.http, methods=tuple(sorted(self.methods)))

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
