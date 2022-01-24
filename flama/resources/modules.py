import inspect
import typing

from flama.modules import Module
from flama.resources.routing import ResourceRoute

if typing.TYPE_CHECKING:
    from flama.resources.resource import BaseResource

__all__ = ["ResourcesModule"]


class ResourcesModule(Module):
    name = "resources"

    def add_resource(
        self, path: str, resource: typing.Union["BaseResource", typing.Type["BaseResource"]], *args, **kwargs
    ):
        """Adds a resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param resource: Resource class.
        """
        # Handle class or instance objects
        resource = resource(app=self.app, *args, **kwargs) if inspect.isclass(resource) else resource

        self.app.routes.append(ResourceRoute(path, resource, main_app=self.app))

    def resource(self, path: str, *args, **kwargs) -> typing.Callable:
        """Decorator for Resources classes for adding them to the application.

        :param path: Resource base path.
        :return: Decorated resource class.
        """

        def decorator(resource: typing.Type["BaseResource"]) -> typing.Type["BaseResource"]:
            self.add_resource(path, resource=resource, *args, **kwargs)
            return resource

        return decorator
