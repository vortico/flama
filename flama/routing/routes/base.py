import abc
import enum
import functools
import logging
import typing as t

from flama import concurrency, exceptions, types, url
from flama.pagination import paginator
from flama.schemas.routing import RouteParametersMixin

if t.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["BaseEndpointWrapper", "BaseRoute"]

logger = logging.getLogger(__name__)


class BaseEndpointWrapper(abc.ABC):
    def __init__(self, handler: types.Handler, *, pagination: t.Optional[types.Pagination] = None):
        """Wraps a function or endpoint into ASGI application.

        :param handler: Function or endpoint.
        :param pagination: Apply a pagination technique.
        """
        if pagination:
            handler = paginator.paginate(pagination, handler)

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


class BaseRoute(abc.ABC, RouteParametersMixin):
    class Match(enum.Enum):
        none = enum.auto()
        partial = enum.auto()
        full = enum.auto()

    def __init__(
        self,
        path: t.Union[str, url.Path],
        app: types.App,
        *,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        tags: t.Optional[dict[str, t.Any]] = None,
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

    def build(self, app: t.Optional["Flama"] = None) -> None:
        """Build step for routes.

        Just build the parameters' descriptor part of RouteParametersMixin.

        :param app: Flama app.
        """
        if app:
            self.parameters.build(app)

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
