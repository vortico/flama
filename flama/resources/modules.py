import inspect
import typing as t

from flama.modules import Module
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    from flama import types
    from flama.resources.resource import BaseResource

__all__ = ["ResourcesModule"]


class ResourcesModule(Module):
    name = "resources"

    def add_resource(
        self,
        path: str,
        resource: t.Union["BaseResource", t.Type["BaseResource"]],
        tags: t.Optional[t.Dict[str, t.Dict[str, "types.Tag"]]] = None,
        *args,
        **kwargs
    ) -> "BaseResource":
        """Adds a resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param tags: Tags to add to the resource.
        :param resource: Resource class.
        """
        # Handle class or instance objects
        resource_instance: "BaseResource" = resource(*args, **kwargs) if inspect.isclass(resource) else resource

        self.app.mount(mount=ResourceRoute(path, resource_instance, tags))

        return resource_instance

    def resource(
        self, path: str, tags: t.Optional[t.Dict[str, t.Dict[str, "types.Tag"]]] = None, *args, **kwargs
    ) -> t.Callable:
        """Decorator for Resources classes for adding them to the application.

        :param path: Resource base path.
        :param tags: Tags to add to the resource.
        :return: Decorated resource class.
        """

        def decorator(resource: t.Type["BaseResource"]) -> t.Type["BaseResource"]:
            self.add_resource(path, resource, tags, *args, **kwargs)
            return resource

        return decorator
