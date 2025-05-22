import logging
import typing as t

from flama import concurrency, exceptions, types, url
from flama.injection import Component, Components
from flama.routing.routes.base import BaseRoute

if t.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["Mount"]

logger = logging.getLogger(__name__)


class Mount(BaseRoute):
    def __init__(
        self,
        path: str,
        app: t.Optional[types.App] = None,
        *,
        routes: t.Optional[t.Sequence[BaseRoute]] = None,
        components: t.Optional[t.Sequence[Component]] = None,
        name: t.Optional[str] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ):
        """A mount point for adding a nested ASGI application or a list of routes.

        :param path: URL path.
        :param app: ASGI application.
        :param routes: List of routes.
        :param components: Components registered under this mount point.
        :param name: Mount name.
        :param tags: Mount tags.
        """
        if app is None and routes is None:
            raise exceptions.ApplicationError("Either 'path' and 'app' or 'mount' variables are needed")

        if app is None:
            from flama.routing.router import Router

            app = Router(routes=routes, components=components)

        super().__init__(path, app, name=name, tags=tags)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] in ("http", "websocket") or (
            scope["type"] == "lifespan" and types.is_flama_instance(self.app)
        ):
            await self.handle(types.Scope({**scope, **self.route_scope(scope)}), receive, send)

    def build(self, app: t.Optional["Flama"] = None) -> None:
        """Build step for routes.

        Just build the parameters' descriptor part of RouteParametersMixin.

        :param app: Flama app.
        """
        if app and types.is_flama_instance(self.app):
            self.app.router.components = Components(self.app.router.components + app.components)

        if root := (self.app if types.is_flama_instance(self.app) else app):
            for route in self.routes:
                route.build(root)

    def match(self, scope: types.Scope) -> BaseRoute.Match:
        """Check if this route matches with given scope.

        :param scope: ASGI scope.
        :return: Match.
        """
        if scope["type"] not in ("http", "websocket"):
            return self.Match.none

        return (
            self.Match.full
            if self.path.match(scope["path"]).match in (self.path.Match.exact, self.path.Match.partial)
            else self.Match.none
        )

    async def handle(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        """Performs a request by calling the app of this route.

        :param scope: ASGI scope.
        :param receive: ASGI receive event.
        :param send: ASGI send event
        """
        await concurrency.run(self.app, scope, receive, send)

    def route_scope(self, scope: types.Scope) -> types.Scope:
        """Build route scope from given scope.

        It generates an updated scope parameters for the route:
        * app: The app of this mount point. If it's mounting a Flama app, it will replace the app with this one
        * path_params: The matched path parameters of this mount point
        * endpoint: The endpoint of this mount point
        * root_path: The root path of this mount point (if it's mounting a Flama app, it will be empty)
        * path: The remaining path to be matched

        :param scope: ASGI scope.
        :return: Route scope.
        """
        is_flama = types.is_flama_instance(self.app)
        result = {"app": self.app if is_flama else scope["app"]}

        if "path" in scope:
            path = scope["path"]
            match = self.path.match(path)
            result.update(
                {
                    "root_path": "" if is_flama else str(url.Path(scope.get("root_path", "")) / (match.matched or "")),
                    "path": str(url.Path("/") / (match.unmatched or "")),
                }
            )

        return types.Scope(result)

    def resolve_url(self, name: str, **params: t.Any) -> url.URL:
        """Builds URL path for given name and params.

        :param name: Route name.
        :param params: Path params.
        :return: URL path.
        """
        try:
            app_name, rest = name.split(":", 1)
        except ValueError:
            app_name, rest = name, None

        if app_name != self.name:
            raise exceptions.NotFoundException(params=params, name=name)

        try:
            path = self.path.build(**params)
        except ValueError:
            raise exceptions.NotFoundException(params=params, name=name)

        if rest is None:
            return url.URL(path=path.path, scheme="http")

        for route in self.routes:
            try:
                route_url = route.resolve_url(rest, **path.unused)
                return url.URL(path=path.path / route_url.path, scheme="http")
            except exceptions.NotFoundException:
                pass

        raise exceptions.NotFoundException(params=params, name=name)

    @property
    def routes(self) -> list[BaseRoute]:
        """Get all routes registered in this Mount.

        :return: List of routes.
        """
        return getattr(self.app, "routes", [])
