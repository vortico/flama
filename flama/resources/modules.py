import inspect
import typing as t

from flama import exceptions
from flama.modules import Module
from flama.resources.resource import Resource
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    try:
        from flama.ddd.repositories.sqlalchemy import SQLAlchemyTableRepository
        from flama.resources.workers import FlamaWorker
    except exceptions.DependencyNotInstalled:
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
        resource: t.Union[Resource, type[Resource]],
        tags: t.Optional[dict[str, dict[str, t.Any]]] = None,
        *args,
        **kwargs,
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

    def resource(self, path: str, tags: t.Optional[dict[str, dict[str, t.Any]]] = None, *args, **kwargs) -> t.Callable:
        """Decorator for Resources classes for adding them to the application.

        :param path: Resource base path.
        :param tags: Tags to add to the resource.
        :return: Decorated resource class.
        """

        def decorator(resource: type[Resource]) -> type[Resource]:
            self.add_resource(path, resource, tags, *args, **kwargs)
            return resource

        return decorator

    def add_repository(self, name: str, repository: type["SQLAlchemyTableRepository"]) -> None:
        """Register a repository.

        :param name: The name of the repository.
        :param repository: The repository class.
        """
        if self.worker:
            self.worker.add_repository(name, repository)

    def remove_repository(self, name: str) -> None:
        """Deregister a repository.

        :param name: The name of the repository.
        """
        if self.worker:
            self.worker.remove_repository(name)
