import inspect
import typing

from flama.routing import BaseRoute, Mount, Route

if typing.TYPE_CHECKING:
    from flama import Flama
    from flama.resources import BaseResource

__all__ = ["ResourceRoute"]


class ResourceRoute(Mount):
    def __init__(
        self, path: str, resource: typing.Union["BaseResource", typing.Type["BaseResource"]], main_app: "Flama" = None
    ):
        # Handle class or instance objects
        self.resource = resource(app=main_app) if inspect.isclass(resource) else resource

        routes = [
            Route(
                path=route._meta.path,
                endpoint=getattr(self.resource, name),
                methods=route._meta.methods,
                name=route._meta.name
                if route._meta.name is not None
                else f"{self.resource._meta.name}-{route.__name__}",
                main_app=main_app,
                **route._meta.kwargs,
            )
            for name, route in self.resource.routes.items()
        ]

        super().__init__(path=path, routes=routes, main_app=main_app)

    @BaseRoute.main_app.setter
    def main_app(self, app: "Flama"):
        BaseRoute.main_app.fset(self, app)
        self.resource.app = app  # Inject app to resource

    @main_app.deleter  # type: ignore[no-redef]
    def main_app(self):
        BaseRoute.main_app.fdel(self)
        del self.resource.app
