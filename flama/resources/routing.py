import inspect
import typing

from flama.routing import Mount, Route

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

        super().__init__(path=path, routes=routes)

        if main_app is not None:
            self.main_app = main_app

    @property
    def main_app(self) -> "Flama":
        if self._main_app is None:
            raise AttributeError("ResourceRoute is not initialized")

        return self._main_app

    @main_app.setter
    def main_app(self, app: "Flama"):
        self._main_app = app

        self.app.main_app = app
        self.resource.app = app  # Inject app to resource
        for route in self.routes:
            route.main_app = app

    @main_app.deleter
    def main_app(self):
        self._main_app = None

        del self.app.main_app
        self.resource.app = None
        for route in self.routes:
            del route.main_app
