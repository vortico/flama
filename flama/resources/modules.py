import inspect
import typing as t

from flama.modules import Module
from flama.resources.resource import Resource
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    try:
        from flama.resources.workers import FlamaWorker
    except AssertionError:
        ...


__all__ = ["ResourcesModule"]


class ResourcesModule(Module):
    name = "resources"

    def __init__(self, worker: t.Optional["FlamaWorker"] = None):
        super().__init__()
        self.worker = worker

    def add_resource(
        self,
        path: str,
        resource: t.Union[Resource, t.Type[Resource]],
        tags: t.Optional[t.Dict[str, t.Dict[str, t.Any]]] = None,
        *args,
        **kwargs
    ) -> "Resource":
        """Adds a resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param tags: Tags to add to the resource.
        :param resource: Resource class.
        """
        if inspect.isclass(resource) and issubclass(resource, Resource):
            resource_instance = resource(*args, **kwargs)
        elif isinstance(resource, Resource):
            resource_instance = resource
        else:
            raise ValueError("Wrong resource")

        self.app.mount(mount=ResourceRoute(path, resource_instance, tags))

        return resource_instance

    def resource(
        self, path: str, tags: t.Optional[t.Dict[str, t.Dict[str, t.Any]]] = None, *args, **kwargs
    ) -> t.Callable:
        """Decorator for Resources classes for adding them to the application.

        :param path: Resource base path.
        :param tags: Tags to add to the resource.
        :return: Decorated resource class.
        """

        def decorator(resource: t.Type[Resource]) -> t.Type[Resource]:
            self.add_resource(path, resource, tags, *args, **kwargs)
            return resource

        return decorator
