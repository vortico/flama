import inspect
import typing

from flama.modules import Module
from flama.resources.routing import ResourceRoute

if typing.TYPE_CHECKING:
    from flama.resources.resource import BaseResource

__all__ = ["ModelsModule"]


class ModelsModule(Module):
    name = "resources"

    def add_model(
        self, path: str, resource: typing.Union["BaseResource", typing.Type["BaseResource"]], *args, **kwargs
    ):
        """Adds a model to this application, setting its endpoints.

        :param path: Resource base path.
        :param resource: Resource class.
        """
        # Handle class or instance objects
        resource = resource(app=self.app, *args, **kwargs) if inspect.isclass(resource) else resource

        self.app.routes.append(ResourceRoute(path, resource, main_app=self.app))

    def model(self, path: str, *args, **kwargs) -> typing.Callable:
        """Decorator for Model classes for adding them to the application.

        :param path: Resource base path.
        :return: Decorated resource class.
        """

        def decorator(resource: typing.Type["BaseResource"]) -> typing.Type["BaseResource"]:
            self.add_model(path, resource, *args, **kwargs)
            return resource

        return decorator
