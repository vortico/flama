import typing

from flama.modules import Module

if typing.TYPE_CHECKING:
    from flama.resources.base import BaseResource

__all__ = ["ResourcesModule"]


class ResourcesModule(Module):
    name = "resources"

    def add_resource(self, path: str, resource: "BaseResource"):
        """Adds a resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param resource: Resource class.
        """
        self.app.router.add_resource(path, resource=resource)

    def resource(self, path: str) -> typing.Callable:
        """Decorator for Resources classes for adding them to the application.

        :param path: Resource base path.
        :return: Decorated resource class.
        """

        def decorator(resource: "BaseResource") -> "BaseResource":
            self.add_resource(path, resource=resource)
            return resource

        return decorator
