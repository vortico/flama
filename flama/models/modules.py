import os
import typing as t

from flama.models.base import BaseLLMModel
from flama.models.components import ModelComponentBuilder
from flama.models.llm_resource import LLMResource, LLMResourceType
from flama.models.ml_resource import MLResource, MLResourceType
from flama.modules import Module
from flama.serialize.data_structures import ModelArtifact

if t.TYPE_CHECKING:
    from flama.resources import ResourceRoute

__all__ = ["ModelsModule"]


class ModelsModule(Module):
    """Application module wiring packaged ML and LLM artifacts into Flama.

    Exposes high-level helpers to register a model artifact under an HTTP path. The artifact's framework metadata
    is auto-detected: ML artifacts (sklearn, torch, tensorflow, transformers) are wrapped in :class:`MLResource`
    while LLM artifacts (vllm) are wrapped in :class:`LLMResource`. Bundled artifacts are tracked on the module
    instance for later introspection.
    """

    name = "models"

    def __init__(self) -> None:
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
        """Register a packaged model under *path*, auto-routing to the appropriate resource type.

        The artifact is loaded via :class:`ModelComponentBuilder.build`; the resulting component's model type
        determines whether the model is wrapped in :class:`MLResource` or :class:`LLMResource`. Extra positional
        and keyword arguments are forwarded to :meth:`add_model_resource`.

        :param path: Mount path for the resource.
        :param model: Filesystem path to the packaged model artifact.
        :param name: Resource name used for OpenAPI tags.
        :param tags: Method-level tags forwarded to the resource.
        :return: The mounted :class:`ResourceRoute`.
        """
        component = ModelComponentBuilder.build(model)

        name_ = name
        component_ = component

        if isinstance(component.model, BaseLLMModel):

            class Resource(LLMResource, metaclass=LLMResourceType):
                name = name_
                component = component_
        else:

            class Resource(MLResource, metaclass=MLResourceType):  # type: ignore[no-redef]
                name = name_
                component = component_

        return self.add_model_resource(path, Resource(), tags, *args, **kwargs)

    def model_resource(self, path: str, tags: dict[str, dict[str, t.Any]] | None = None, *args, **kwargs) -> t.Callable:
        """Decorator registering an :class:`MLResource` or :class:`LLMResource` subclass at *path*.

        Extra positional and keyword arguments are forwarded to :meth:`add_model_resource`.

        :param path: Mount path for the resource.
        :param tags: Method-level tags forwarded to the resource.
        :return: Decorator returning the original resource class unchanged.
        """

        def decorator(resource: type[MLResource | LLMResource]) -> type[MLResource | LLMResource]:
            self.add_model_resource(path, resource, tags, *args, **kwargs)
            return resource

        return decorator

    def add_model_resource(
        self,
        path: str,
        resource: MLResource | LLMResource | type[MLResource | LLMResource],
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        **kwargs,
    ) -> "ResourceRoute":
        """Register an :class:`MLResource` or :class:`LLMResource` instance/class under *path*.

        The resource's component is added to the app, its bundled artifact (if any) is tracked locally for later
        introspection, and the resulting :class:`ResourceRoute` is mounted. Extra arguments are forwarded to
        :meth:`Resources.add_resource`.

        :param path: Mount path for the resource.
        :param resource: Resource instance or class.
        :param tags: Method-level tags forwarded to the resource.
        :return: The mounted :class:`ResourceRoute`.
        """
        if resource.component._artifact is not None:
            self._artifacts.append(resource.component._artifact)

        self.app.add_component(resource.component)
        return self.app.resources.add_resource(path, resource, *args, tags=tags, **kwargs)
