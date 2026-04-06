import abc
import dataclasses
import enum
import functools
import inspect
import logging
import typing as t

from flama import concurrency, exceptions, types, url
from flama.pagination import paginator
from flama.schemas.routing import ParametersDescriptor
from flama.types.http import Method

__all__ = ["BaseEndpointWrapper", "BaseRoute", "ResolveResult", "ResolveType", "RouteTableParams", "ScopeType"]

logger = logging.getLogger(__name__)


class ScopeType(enum.IntFlag):
    http = 0b01
    websocket = 0b10
    all = http | websocket


@dataclasses.dataclass(frozen=True, slots=True)
class RouteTableParams:
    scope_type: ScopeType
    accept_partial_path: bool = False
    methods: tuple[Method, ...] | None = None


class ResolveType(enum.Enum):
    full = enum.auto()
    mount = enum.auto()
    method_not_allowed = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True)
class ResolveResult:
    type: ResolveType
    index: int
    params: tuple[str, ...] = ()
    matched: str | None = None
    unmatched: str | None = None
    allowed_methods: tuple[Method, ...] | None = None


class BaseEndpointWrapper(abc.ABC):
    def __init__(
        self,
        handler: types.Handler,
        /,
        *,
        signature: inspect.Signature | None = None,
        pagination: types.Pagination | None = None,
    ):
        """Wraps a function or endpoint into ASGI application.

        :param handler: Function or endpoint.
        :param signature: Handler signature.
        :param pagination: Apply a pagination technique.
        """
        if pagination:
            handler = paginator.apply(pagination, handler, signature=signature)

        self.handler = handler
        functools.update_wrapper(self, handler)

    def __get__(self, instance, owner):
        return functools.partial(self.__call__, instance)

    @abc.abstractmethod
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive.
        :param send: ASGI send.
        """
        ...

    def __hash__(self) -> int:
        return hash(self.handler)

    def __eq__(self, other) -> bool:
        return isinstance(other, BaseEndpointWrapper) and self.handler == other.handler


class BaseRoute(types.BaseRoute, abc.ABC):
    class Match(enum.Enum):
        none = enum.auto()
        partial = enum.auto()
        full = enum.auto()

    def __init__(
        self,
        path: str | url.Path,
        app: t.Any,
        *,
        name: str | None = None,
        include_in_schema: bool = True,
        tags: dict[str, t.Any] | None = None,
    ):
        """A route definition of a http endpoint.

        :param path: URL path.
        :param app: ASGI application.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param tags: Route tags.
        """
        self.path = url.Path(path)
        self.app = app
        self.endpoint = app.handler if isinstance(app, BaseEndpointWrapper) else app
        self.name = name
        self.include_in_schema = include_in_schema
        self.tags = tags or {}
        self.parameters = ParametersDescriptor(self)
        super().__init__()

    @abc.abstractmethod
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None: ...

    def __hash__(self) -> int:
        return hash((self.app, self.path, self.name))

    def __eq__(self, other: t.Any) -> bool:
        return (
            isinstance(other, BaseRoute)
            and self.path == other.path
            and self.app == other.app
            and self.name == other.name
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r}, name={(self.name or '')!r})"

    def _build(self, app: types.App) -> None:
        """Build step for routes.

        Just build the parameters' descriptor part of RouteParametersMixin.

        :param app: Flama app.
        """
        self.parameters._build(app)

    def endpoint_handlers(self) -> dict[str, t.Callable]:
        """Return a mapping of all possible endpoints of this route.

        Useful to identify all endpoints by HTTP methods.

        :return: Mapping of all endpoints.
        """
        return {}

    async def handle(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request by calling the app of this route.

        :param scope: ASGI scope.
        :param receive: ASGI receive event.
        :param send: ASGI send event.
        """
        await concurrency.run(self.app, scope, receive, send)

    def match(self, scope: types.Scope) -> Match:
        """Check if this route matches with given scope.

        :param scope: ASGI scope.
        :return: Match.
        """
        return self.Match.full if self.path.match(scope["path"]).match == self.path.Match.exact else self.Match.none

    def route_scope(self, scope: types.Scope) -> types.Scope:
        """Build route scope from given scope.

        :param scope: ASGI scope.
        :return: Route scope.
        """
        return types.Scope({})

    @property
    def _route_table_params(self) -> RouteTableParams:
        """Configuration for the Rust RouteTable entry."""
        return RouteTableParams(scope_type=ScopeType(0))

    def resolve_url(self, name: str, **params: t.Any) -> url.URL:
        """Builds URL path for given name and params.

        :param name: Route name.
        :param params: Path params.
        :return: URL path.
        """
        if name != self.name:
            raise exceptions.NotFoundException(params=params, name=name)

        try:
            result = self.path.build(**params)
        except ValueError:
            raise exceptions.NotFoundException(params=params, name=name)

        if result.unused:
            raise exceptions.NotFoundException(params=params, name=name)

        return url.URL(path=result.path, scheme="http")
