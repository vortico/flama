import functools
import logging
import threading
import typing as t

from flama import asgi, exceptions, http, injection, types, url, validation, websockets
from flama.ddd.components import WorkerComponent
from flama.events import Events
from flama.middleware import MiddlewareStack
from flama.models.modules import ModelsModule
from flama.modules import Modules
from flama.pagination import paginator
from flama.resources import ResourcesModule
from flama.routing import BaseRoute, Router
from flama.schemas.modules import SchemaModule

try:
    from flama.resources.workers import FlamaWorker
except exceptions.DependencyNotInstalled:
    FlamaWorker = None

if t.TYPE_CHECKING:
    from flama.middleware import Middleware
    from flama.modules import Module
    from flama.pagination.types import PaginationType
    from flama.routing import Mount, Route, WebSocketRoute

__all__ = ["Flama"]

logger = logging.getLogger(__name__)


class Flama:
    def __init__(
        self,
        routes: t.Optional[t.Sequence[t.Union["BaseRoute", "Mount"]]] = None,
        components: t.Optional[t.Union[t.Sequence[injection.Component], set[injection.Component]]] = None,
        modules: t.Optional[t.Union[t.Sequence["Module"], set["Module"]]] = None,
        middleware: t.Optional[t.Sequence["Middleware"]] = None,
        debug: bool = False,
        events: t.Optional[t.Union[dict[str, list[t.Callable[..., t.Coroutine[t.Any, t.Any, None]]]], Events]] = None,
        lifespan: t.Optional[t.Callable[[t.Optional["Flama"]], t.AsyncContextManager]] = None,
        title: str = "Flama",
        version: str = "0.1.0",
        description: str = "Firing up with the flame",
        schema: t.Optional[str] = "/schema/",
        docs: t.Optional[str] = "/docs/",
        schema_library: t.Optional[str] = None,
    ) -> None:
        """Flama application.

        :param routes: Routes part of this application.
        :param components: Components registered in this application.
        :param modules: Modules for extending the application.
        :param middleware: List of middlewares to include in call stack.
        :param debug: Debug mode.
        :param events: Handlers that will be triggered after certain events.
        :param lifespan: Lifespan function.
        :param title: API title.
        :param version: API version.
        :param description: API description.
        :param schema: OpenAPI schema endpoint path.
        :param docs: Docs endpoint path.
        :param schema_library: Schema library to use.
        """
        self._debug = debug
        self._status = types.AppStatus.NOT_STARTED
        self._shutdown = False

        # Create Dependency Injector
        self._injector = injection.Injector(
            context_types={
                "scope": types.Scope,
                "receive": types.Receive,
                "send": types.Send,
                "exc": Exception,
                "app": Flama,
                "path_params": types.PathParams,
                "route": BaseRoute,
                "request": http.Request,
                "response": http.Response,
                "websocket": websockets.WebSocket,
                "websocket_message": types.Message,
                "websocket_encoding": types.Encoding,
                "websocket_code": types.Code,
            }
        )

        # Initialise components
        default_components = []

        # Create worker
        if (worker := FlamaWorker() if FlamaWorker else None) and WorkerComponent:
            default_components.append(WorkerComponent(worker=worker))

        # Initialise modules
        default_modules = [
            ResourcesModule(worker=worker),
            SchemaModule(title, version, description, schema=schema, docs=docs),
            ModelsModule(),
        ]
        self.modules = Modules(app=self, modules={*default_modules, *(modules or [])})

        # Initialize router
        self.app = self.router = Router(
            routes=routes, components=[*default_components, *(components or [])], lifespan=lifespan
        )

        # Build middleware stack
        self.middleware = MiddlewareStack(app=self, middleware=middleware or [], debug=debug)

        # Setup schema library
        self.schema.schema_library = schema_library

        # Add schema routes
        self.schema.add_routes()

        # Build events register including module events
        self.events = events if isinstance(events, Events) else Events.build(**(events or {}))
        self.events.startup += [m.on_startup for m in self.modules.values()]
        self.events.shutdown += [m.on_shutdown for m in self.modules.values()]

        # Reference to paginator from within app
        self.paginator = paginator

        # Build router to propagate root application
        self.router.build(self)

    def __getattr__(self, item: str) -> t.Any:
        """Retrieve a module by its name.

        :param item: Module name.
        :return: Module.
        """
        try:
            return self.modules.__getitem__(item)
        except KeyError:
            return None  # type: ignore[return-value]

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Perform a request.

        :param scope: ASGI scope.
        :param receive: ASGI receive event.
        :param send: ASGI send event.
        """
        if scope["type"] != "lifespan" and self.status in (types.AppStatus.NOT_STARTED, types.AppStatus.STARTING):
            raise exceptions.ApplicationError("Application is not ready to process requests yet.")

        if scope["type"] != "lifespan" and self.status in (types.AppStatus.SHUT_DOWN, types.AppStatus.SHUTTING_DOWN):
            raise exceptions.ApplicationError("Application is already shut down.")

        scope["app"] = self
        scope.setdefault("root_app", self)
        await self.middleware(scope, receive, send)

    @property
    def status(self) -> types.AppStatus:
        return self._status

    @status.setter
    def status(self, s: types.AppStatus) -> None:
        logger.debug("Transitioning %s from %s to %s", self, self._status, s)

        with threading.Lock():
            self._status = s

    @property
    def components(self) -> injection.Components:
        """Components register.

        :return: Components register.
        """
        return self.router.components

    def add_component(self, component: injection.Component):
        """Add a new component to the register.

        :param component: Component to include.
        """
        self.router.add_component(component)
        self.router.build(self)

    @property
    def routes(self) -> list["BaseRoute"]:
        """List of registered routes.

        :return: Routes.
        """
        return self.router.routes

    def add_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.HTTPHandler] = None,
        methods: t.Optional[list[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        route: t.Optional["Route"] = None,
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> "Route":
        """Register a new HTTP route or endpoint under given path.

        :param path: URL path.
        :param endpoint: HTTP endpoint.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param route: HTTP route.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the route.
        """
        return self.router.add_route(
            path,
            endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
            route=route,
            root=self,
            pagination=pagination,
            tags=tags,
        )

    def route(
        self,
        path: str,
        methods: t.Optional[list[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> t.Callable[[types.HTTPHandler], types.HTTPHandler]:
        """Decorator version for registering a new HTTP route in this router under given path.

        :param path: URL path.
        :param methods: List of valid HTTP methods (only applies for routes).
        :param name: Endpoint or route name.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the route.
        :return: Decorated route.
        """
        return self.router.route(
            path,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
            root=self,
            pagination=pagination,
            tags=tags,
        )

    def add_websocket_route(
        self,
        path: t.Optional[str] = None,
        endpoint: t.Optional[types.WebSocketHandler] = None,
        name: t.Optional[str] = None,
        route: t.Optional["WebSocketRoute"] = None,
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> "WebSocketRoute":
        """Register a new websocket route or endpoint under given path.

        :param path: URL path.
        :param endpoint: Websocket endpoint.
        :param name: Endpoint or route name.
        :param route: Websocket route.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the websocket route.
        """
        return self.router.add_websocket_route(
            path, endpoint, name=name, route=route, root=self, pagination=pagination, tags=tags
        )

    def websocket_route(
        self,
        path: str,
        name: t.Optional[str] = None,
        pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> t.Callable[[types.WebSocketHandler], types.WebSocketHandler]:
        """Decorator version for registering a new websocket route in this router under given path.

        :param path: URL path.
        :param name: Websocket route name.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the websocket route.
        :return: Decorated route.
        """
        return self.router.websocket_route(path, name=name, root=self, pagination=pagination, tags=tags)

    def mount(
        self,
        path: t.Optional[str] = None,
        app: t.Optional[types.App] = None,
        name: t.Optional[str] = None,
        mount: t.Optional["Mount"] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> "Mount":
        """Register a new mount point containing an ASGI app in this router under given path.

        :param path: URL path.
        :param app: ASGI app to mount.
        :param name: Application name.
        :param mount: Mount.
        :param tags: Tags to add to the mount.
        :return: Mount.
        """
        return self.router.mount(path, app, name=name, mount=mount, root=self, tags=tags)

    @property
    def injector(self) -> injection.Injector:
        """Components dependency injector.

        :return: Injector instance.
        """
        components = injection.Components(self.components + asgi.ASGI_COMPONENTS + validation.VALIDATION_COMPONENTS)
        if self._injector.components != components:
            self._injector.components = components
        return self._injector

    def add_event_handler(self, event: str, func: t.Callable) -> None:
        """Register a new event handler.

        :param event: Event type.
        :param func: Event handler.
        """
        self.events.register(event, func)

    def on_event(self, event: str) -> t.Callable:
        """Decorator version for registering a new event handler.

        :param event: Event type.
        :return: Decorated handler.
        """

        def decorator(func: t.Callable) -> t.Callable:
            self.add_event_handler(event, func)
            return func

        return decorator

    def add_exception_handler(self, exc_class_or_status_code: t.Union[int, type[Exception]], handler: t.Callable):
        """Add a new exception handler for given status code or exception class.

        :param exc_class_or_status_code: Status code or exception class.
        :param handler: Exception handler.
        """
        self.middleware.add_exception_handler(exc_class_or_status_code, handler)

    def add_middleware(self, middleware: "Middleware"):
        """Add a new middleware to the stack.

        :param middleware: Middleware instance.
        """
        self.middleware.add_middleware(middleware)

    def resolve_url(self, name: str, **path_params: t.Any) -> url.URL:
        """Look for a route URL given the route name and path params.

        :param name: Route name.
        :param path_params: Path params.
        :return: Route URL.
        """
        return self.router.resolve_url(name, **path_params)

    def resolve_route(self, scope: types.Scope) -> tuple[BaseRoute, types.Scope]:
        """Look for a route that matches given ASGI scope.

        :param scope: ASGI scope.
        :return: Route and its scope.
        """
        return self.router.resolve_route(scope)

    get = functools.partialmethod(route, methods=["GET"])
    head = functools.partialmethod(route, methods=["HEAD"])
    post = functools.partialmethod(route, methods=["POST"])
    put = functools.partialmethod(route, methods=["PUT"])
    delete = functools.partialmethod(route, methods=["DELETE"])
    connect = functools.partialmethod(route, methods=["CONNECT"])
    options = functools.partialmethod(route, methods=["OPTIONS"])
    trace = functools.partialmethod(route, methods=["TRACE"])
    patch = functools.partialmethod(route, methods=["PATCH"])
    add_get = functools.partialmethod(add_route, methods=["GET"])
    add_head = functools.partialmethod(add_route, methods=["HEAD"])
    add_post = functools.partialmethod(add_route, methods=["POST"])
    add_put = functools.partialmethod(add_route, methods=["PUT"])
    add_delete = functools.partialmethod(add_route, methods=["DELETE"])
    add_connect = functools.partialmethod(add_route, methods=["CONNECT"])
    add_options = functools.partialmethod(add_route, methods=["OPTIONS"])
    add_trace = functools.partialmethod(add_route, methods=["TRACE"])
    add_patch = functools.partialmethod(add_route, methods=["PATCH"])
