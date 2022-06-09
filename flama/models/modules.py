import os
import typing

from flama.models.resource import ModelResource, ModelResourceType
from flama.modules import Module

__all__ = ["ModelsModule"]


class ModelsModule(Module):
    name = "models"

    def add_model(self, path: str, model: typing.Union[str, os.PathLike], name: str, *args, **kwargs):
        """Adds a model to this application, setting its endpoints.

        :param path: Resource base path.
        :param model: Model path.
        :param name: Model name.
        """
        name_ = name
        model_ = model

        class Resource(ModelResource, metaclass=ModelResourceType):
            name = name_
            model = model_

        resource = Resource()
        self.app.resources.add_resource(path, resource)  # type: ignore[attr-defined]
        self.app.add_component(resource.component)  # type: ignore

    def model(self, path: str, *args, **kwargs) -> typing.Callable:
        """Decorator for Model classes for adding them to the application.

        :param path: Resource base path.
        :return: Decorated resource class.
        """

        def decorator(resource: typing.Type["BaseResource"]) -> typing.Type["BaseResource"]:
            self.add_model(path, resource, *args, **kwargs)
            return resource

        return decorator
