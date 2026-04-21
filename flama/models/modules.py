import os
import typing as t

from flama.models.llm_resource import LLMResource, LLMResourceType
from flama.models.resource import MLResource, MLResourceType
from flama.modules import Module
from flama.serialize.data_structures import ModelArtifact

if t.TYPE_CHECKING:
    from flama.resources import ResourceRoute

__all__ = ["ModelsModule"]


class ModelsModule(Module):
    name = "models"

    def __init__(self):
        super().__init__()
        self._artifacts: list[ModelArtifact] = []

    def add_model(
        self,
        path: str,
        model: str | os.PathLike,
        name: str,
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        **kwargs,
    ) -> "ResourceRoute":
        """Adds an ML model to this application, setting its endpoints.

        :param path: Resource base path.
        :param model: Model path.
        :param name: Model name.
        :param tags: Tags to add to the model methods.
        """

        name_ = name
        model_ = model

        class Resource(MLResource, metaclass=MLResourceType):
            name = name_
            model_path = model_

        resource = Resource()

        return self.add_model_resource(path, resource, tags, *args, **kwargs)

    def model_resource(self, path: str, tags: dict[str, dict[str, t.Any]] | None = None, *args, **kwargs) -> t.Callable:
        """Decorator for MLResource classes for adding them to the application.

        :param path: Resource base path.
        :param tags: Tags to add to the model methods.
        :return: Decorated resource class.
        """

        def decorator(resource: type[MLResource]) -> type[MLResource]:
            self.app.models.add_model_resource(path, resource, tags, *args, **kwargs)
            return resource

        return decorator

    def add_model_resource(
        self,
        path: str,
        resource: MLResource | type[MLResource],
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        **kwargs,
    ) -> "ResourceRoute":
        """Adds an ML resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param resource: Resource class.
        :param tags: Tags to add to the model methods.
        """
        if resource.component._artifact is not None:
            self._artifacts.append(resource.component._artifact)

        self.app.add_component(resource.component)
        return self.app.resources.add_resource(path, resource, *args, tags=tags, **kwargs)

    def add_llm(
        self,
        path: str,
        model: str | os.PathLike,
        name: str,
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        **kwargs,
    ) -> "ResourceRoute":
        """Adds an LLM to this application, setting its endpoints.

        :param path: Resource base path.
        :param model: Model path.
        :param name: Model name.
        :param tags: Tags to add to the model methods.
        """

        name_ = name
        model_ = model

        class Resource(LLMResource, metaclass=LLMResourceType):
            name = name_
            model_path = model_

        resource = Resource()

        return self.add_llm_resource(path, resource, tags, *args, **kwargs)

    def llm_resource(self, path: str, tags: dict[str, dict[str, t.Any]] | None = None, *args, **kwargs) -> t.Callable:
        """Decorator for LLMResource classes for adding them to the application.

        :param path: Resource base path.
        :param tags: Tags to add to the model methods.
        :return: Decorated resource class.
        """

        def decorator(resource: type[LLMResource]) -> type[LLMResource]:
            self.app.models.add_llm_resource(path, resource, tags, *args, **kwargs)
            return resource

        return decorator

    def add_llm_resource(
        self,
        path: str,
        resource: LLMResource | type[LLMResource],
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        **kwargs,
    ) -> "ResourceRoute":
        """Adds an LLM resource to this application, setting its endpoints.

        :param path: Resource base path.
        :param resource: Resource class.
        :param tags: Tags to add to the model methods.
        """
        if resource.component._artifact is not None:
            self._artifacts.append(resource.component._artifact)

        self.app.add_component(resource.component)
        return self.app.resources.add_resource(path, resource, *args, tags=tags, **kwargs)
