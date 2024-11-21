import os
import typing as t

from flama.models.resource import ModelResource, ModelResourceType
from flama.modules import Module

__all__ = ["ModelsModule"]


class ModelsModule(Module):
    name = "models"

    def add_model(
        self,
        path: str,
        model: t.Union[str, os.PathLike],
        name: str,
        tags: t.Optional[dict[str, dict[str, t.Any]]] = None,
        *args,
        **kwargs,
    ) -> ModelResource:
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
        self.app.resources.add_resource(path, resource, tags=tags, *args, **kwargs)  # type: ignore[attr-defined]
        return resource

    def model_resource(
        self, path: str, tags: t.Optional[dict[str, dict[str, t.Any]]] = None, *args, **kwargs
    ) -> t.Callable:
        """Decorator for ModelResource classes for adding them to the application.

        :param path: Resource base path.
        :param tags: Tags to add to the model methods.
        :return: Decorated resource class.
        """

        def decorator(resource: type[ModelResource]) -> type[ModelResource]:
            self.app.add_component(resource.component)
            self.app.resources.add_resource(path, resource, tags=tags, *args, **kwargs)  # type: ignore[attr-defined]
            return resource

        return decorator

    def add_model_resource(
        self,
        path: str,
        resource: t.Union[ModelResource, type[ModelResource]],
        tags: t.Optional[dict[str, dict[str, t.Any]]] = None,
        *args,
        **kwargs,
    ) -> ModelResource:
        """Adds a resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param resource: Resource class.
        :param tags: Tags to add to the model methods.
        """
        self.app.add_component(resource.component)
        resource_instance: ModelResource = self.app.resources.add_resource(  # type: ignore[attr-defined]
            path, resource, tags=tags, *args, **kwargs
        )
        return resource_instance
