import inspect
import typing as t

from flama import exceptions, types
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
        *args,
        include_in_schema: bool = True,
        tags: t.Optional[dict[str, dict[str, t.Any]]] = None,
        **kwargs,
    ) -> "Resource":
        """Adds a resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param resource: Resource class.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param tags: Tags to add to the resource.
        """
        if inspect.isclass(resource) and issubclass(resource, Resource):
            resource_instance = resource(*args, **kwargs)
        elif isinstance(resource, Resource):
            resource_instance = resource
        else:
            raise ValueError("Wrong resource")

        self.app.mount(mount=ResourceRoute(path, resource_instance, include_in_schema=include_in_schema, tags=tags))

        return resource_instance

    def resource(
        self,
        path: str,
        *args,
        include_in_schema: bool = True,
        tags: t.Optional[dict[str, dict[str, t.Any]]] = None,
        **kwargs,
    ) -> t.Callable:
        """Decorator for Resources classes for adding them to the application.

        :param path: Resource base path.
        :param include_in_schema: True if this route or endpoint should be declared as part of the API schema.
        :param tags: Tags to add to the resource.
        :return: Decorated resource class.
        """

        def decorator(resource: type[Resource]) -> type[Resource]:
            self.add_resource(path, resource, *args, include_in_schema=include_in_schema, tags=tags, **kwargs)
            return resource

        return decorator

    def method(
        self,
        path: str,
        *,
        methods: t.Optional[t.Sequence[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        pagination: t.Optional[types.Pagination] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> t.Callable:
        """Decorator for adding useful info needed for generating resource routes.

        :param path: Route path.
        :param methods: HTTP methods available.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the method.
        :return: Decorated method.
        """
        return ResourceRoute.method(
            path, methods=methods, name=name, include_in_schema=include_in_schema, pagination=pagination, tags=tags
        )

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
