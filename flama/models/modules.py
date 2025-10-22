import os
import typing as t

from flama.models.resource import ModelResource, ModelResourceType
from flama.modules import Module

if t.TYPE_CHECKING:
    from flama.resources import ResourceRoute

__all__ = ["ModelsModule"]


class ModelsModule(Module):
    name = "models"

    def add_model(
        self,
        path: str,
        model: str | os.PathLike,
        name: str,
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        **kwargs,
    ) -> "ResourceRoute":
        """Adds a model to this application, setting its endpoints.

        :param path: Resource base path.
        :param model: Model path.
        :param name: Model name.
        :param tags: Tags to add to the model methods.
        """

        name_ = name
        model_ = model

        class Resource(ModelResource, metaclass=ModelResourceType):
            name = name_
            model_path = model_

        resource = Resource()
        self.app.add_component(resource.component)
        return self.app.resources.add_resource(path, resource, tags=tags, *args, **kwargs)

    def model_resource(self, path: str, tags: dict[str, dict[str, t.Any]] | None = None, *args, **kwargs) -> t.Callable:
        """Decorator for ModelResource classes for adding them to the application.

        :param path: Resource base path.
        :param tags: Tags to add to the model methods.
        :return: Decorated resource class.
        """

        def decorator(resource: type[ModelResource]) -> type[ModelResource]:
            self.app.models.add_model_resource(path, resource, tags=tags, *args, **kwargs)
            return resource

        return decorator

    def add_model_resource(
        self,
        path: str,
        resource: ModelResource | type[ModelResource],
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        **kwargs,
    ) -> "ResourceRoute":
        """Adds a resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param resource: Resource class.
        :param tags: Tags to add to the model methods.
        """
        self.app.add_component(resource.component)
        return self.app.resources.add_resource(path, resource, tags=tags, *args, **kwargs)
