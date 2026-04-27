import os
import typing as t

import flama.schemas
from flama import types
from flama._core.json_encoder import encode_json
from flama.http.responses.sse import ServerSentEventResponse
from flama.models.components import LLMModelComponentBuilder
from flama.models.ml_resource import InspectMixin
from flama.resources import data_structures
from flama.resources.exceptions import ResourceAttributeError
from flama.resources.resource import Resource, ResourceType
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    from flama.models.base import BaseLLMModel
    from flama.models.components import ModelComponent

__all__ = ["BaseLLMResource", "LLMResource", "ConfigureMixin", "QueryMixin", "LLMStreamMixin", "LLMResourceType"]


Component = t.TypeVar("Component", bound="ModelComponent")


class ConfigureMixin:
    @classmethod
    def _add_configure(
        cls, name: str, verbose_name: str, model_model_type: type["BaseLLMModel"], **kwargs
    ) -> dict[str, t.Any]:
        @ResourceRoute.method("/", methods=["PUT"], name="configure")
        async def configure(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(flama.schemas.schemas.LLMConfigureInput)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(flama.schemas.schemas.LLMConfigureOutput)]:
            model.configure(data["params"])
            return {"params": model.params}

        configure.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Configure the model
            description:
                Configure the default generation parameters for this LLM resource.
            responses:
                200:
                    description:
                        The current generation parameters.
        """

        return {"_configure": configure}


class QueryMixin:
    @classmethod
    def _add_query(
        cls, name: str, verbose_name: str, model_model_type: type["BaseLLMModel"], **kwargs
    ) -> dict[str, t.Any]:
        @ResourceRoute.method("/query/", methods=["POST"], name="query")
        async def query(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(flama.schemas.schemas.LLMQueryInput)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(flama.schemas.schemas.LLMQueryOutput)]:
            return {"output": await model.query(data["prompt"], **data.get("params", {}))}

        query.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Query the model
            description:
                Send a prompt to the LLM and get a buffered response.
            responses:
                200:
                    description:
                        The model output.
        """

        return {"_query": query}


class LLMStreamMixin:
    @classmethod
    def _add_stream(
        cls, name: str, verbose_name: str, model_model_type: type["BaseLLMModel"], **kwargs
    ) -> dict[str, t.Any]:
        @ResourceRoute.method("/stream/", methods=["POST"], name="stream")
        async def stream(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(flama.schemas.schemas.LLMStreamInput)],
        ) -> ServerSentEventResponse:
            async def _encode():
                async for item in model.stream(data["prompt"], **data.get("params", {})):
                    yield encode_json(item, compact=True).decode()

            return ServerSentEventResponse(_encode())

        stream.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Stream output
            description:
                Send a prompt to the LLM and stream the response via Server-Sent Events.
            responses:
                200:
                    description:
                        An SSE stream of output tokens.
        """

        return {"_stream": stream}


class LLMResourceType(ResourceType, InspectMixin, ConfigureMixin, QueryMixin, LLMStreamMixin):
    METHODS = ("inspect", "configure", "query", "stream")

    def __new__(mcs, name: str, bases: tuple[type], namespace: dict[str, t.Any]):
        """Resource metaclass for defining basic behavior for LLM resources:
        * Create _meta attribute containing some metadata (model...).
        * Adds methods related to LLM resource (inspect, configure, query, stream) listed in METHODS class attribute.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        """
        if not mcs._is_abstract(namespace):
            try:
                component = mcs._get_model_component(bases, namespace)
                namespace["component"] = component
                namespace["model"] = component.model
            except AttributeError as e:
                raise ResourceAttributeError(str(e), name)

            namespace.setdefault("_meta", data_structures.Metadata()).namespaces["model"] = {
                "component": component,
                "model": component.model,
                "model_type": component.get_model_type(),
            }

        return super().__new__(mcs, name, bases, namespace)

    @staticmethod
    def _is_abstract(namespace: dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.models.llm_resource" and namespace.get("__qualname__") in (
            "BaseLLMResource",
            "LLMResource",
        )

    @classmethod
    def _get_model_component(cls, bases: t.Sequence[t.Any], namespace: dict[str, t.Any]) -> "ModelComponent":
        try:
            return cls._get_attribute("component", bases, namespace, metadata_namespace="model")
        except AttributeError:
            ...

        try:
            return LLMModelComponentBuilder.load(
                cls._get_attribute("model_path", bases, namespace, metadata_namespace="model")
            )
        except AttributeError:
            ...

        raise AttributeError(ResourceAttributeError.MODEL_NOT_FOUND)


class BaseLLMResource(Resource, t.Generic[Component], metaclass=LLMResourceType):
    component: Component
    model: t.Any
    model_path: str | os.PathLike


class LLMResource(BaseLLMResource["ModelComponent"]): ...
