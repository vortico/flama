import abc
import enum
import typing as t

from flama.types.asgi import Receive, Scope, Send

if t.TYPE_CHECKING:
    from flama.events import Events
    from flama.injection.components import Component, Components
    from flama.injection.injector import Injector
    from flama.middleware import Middleware, MiddlewareStack
    from flama.models.modules import ModelsModule
    from flama.modules import Modules
    from flama.resources.modules import ResourcesModule
    from flama.routing import BaseRoute, Mount, Route, Router, WebSocketRoute
    from flama.schemas.modules import SchemaModule
    from flama.sqlalchemy import SQLAlchemyModule
    from flama.types.asgi import HTTPHandler, WebSocketHandler
    from flama.types.http import Method
    from flama.types.pagination import Pagination
    from flama.url import URL


__all__ = ["App", "AppStatus", "is_flama_instance", "is_router_instance"]


class AppStatus(enum.Enum):
    NOT_STARTED = enum.auto()
    STARTING = enum.auto()
    READY = enum.auto()
    SHUTTING_DOWN = enum.auto()
    SHUT_DOWN = enum.auto()
    FAILED = enum.auto()


class App(abc.ABC):
    """Base type for the Flama application.

    Defines the public interface that the application exposes, allowing it to be imported without circular
    dependencies across the framework.
    """

    router: "Router"
    app: "Router"
    parent: "App | None"
    events: "Events"
    modules: "Modules"
    middleware: "MiddlewareStack"
    paginator: t.Any
    schema: "SchemaModule"
    sqlalchemy: "SQLAlchemyModule"
    resources: "ResourcesModule"
    models: "ModelsModule"

    @property
    @abc.abstractmethod
    def status(self) -> AppStatus: ...

    @status.setter
    @abc.abstractmethod
    def status(self, s: AppStatus) -> None: ...

    @property
    @abc.abstractmethod
    def injector(self) -> "Injector": ...

    @property
    @abc.abstractmethod
    def components(self) -> "Components": ...

    @property
    @abc.abstractmethod
    def routes(self) -> "list[BaseRoute]": ...

    @abc.abstractmethod
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...

    @abc.abstractmethod
    def resolve_route(self, scope: Scope) -> "tuple[BaseRoute, Scope]": ...

    @abc.abstractmethod
    def resolve_url(self, name: str, **path_params: t.Any) -> "URL": ...

    def add_component(self, component: "Component") -> None: ...

    @abc.abstractmethod
    def add_route(
        self,
        path: str | None = None,
        endpoint: "HTTPHandler | None" = None,
        methods: "t.Sequence[Method] | None" = None,
        *,
        name: str | None = None,
        include_in_schema: bool = True,
        route: "Route | None" = None,
        pagination: "Pagination | None" = None,
        tags: dict[str, t.Any] | None = None,
    ) -> "Route": ...

    @abc.abstractmethod
    def add_websocket_route(
        self,
        path: str | None = None,
        endpoint: "WebSocketHandler | None" = None,
        *,
        name: str | None = None,
        route: "WebSocketRoute | None" = None,
        pagination: "Pagination | None" = None,
        tags: dict[str, t.Any] | None = None,
    ) -> "WebSocketRoute": ...

    @abc.abstractmethod
    def mount(
        self,
        path: str | None = None,
        app: "t.Any | None" = None,
        *,
        name: str | None = None,
        mount: "Mount | None" = None,
        tags: dict[str, t.Any] | None = None,
    ) -> "Mount": ...

    def add_event_handler(self, event: str, func: t.Callable) -> None: ...

    @abc.abstractmethod
    def on_event(self, event: str) -> t.Callable: ...

    def add_exception_handler(self, exc_class_or_status_code: int | type[Exception], handler: t.Callable) -> None: ...

    def add_middleware(self, middleware: "Middleware") -> None: ...


def is_flama_instance(obj: t.Any) -> t.TypeGuard["App"]:
    """Checks if an object is an instance of a Flama App.

    :param obj: The object to check.
    :return: True if the object is an instance of App, False otherwise.
    """
    return isinstance(obj, App)


def is_router_instance(obj: t.Any) -> t.TypeGuard["Router"]:
    """Checks if an object is an instance of Flama's Router.

    :param obj: The object to check.
    :return: True if the object is an instance of Router, False otherwise.
    """
    from flama.routing import Router

    return isinstance(obj, Router)
