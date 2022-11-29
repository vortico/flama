import os
import typing as t

import flama.schemas
from flama.models.components import ModelComponentBuilder
from flama.resources import BaseResource, data_structures
from flama.resources.exceptions import ResourceAttributeError
from flama.resources.resource import ResourceType
from flama.resources.routing import resource_method

if t.TYPE_CHECKING:
    from flama.models.components import Model, ModelComponent

__all__ = ["ModelResource", "InspectMixin", "PredictMixin", "ModelResourceType"]


class InspectMixin:
    @classmethod
    def _add_inspect(mcs, name: str, verbose_name: str, model_model_type: "Model", **kwargs) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["GET"], name=f"{name}-inspect")
        async def inspect(self, model: model_model_type):  # type: ignore[valid-type]
            return model.inspect()  # type: ignore[attr-defined]

        inspect.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Retrieve the model.
            description:
                Retrieve the model from this resource.
            responses:
                200:
                    description:
                        The model.
        """

        return {"_inspect": inspect}


class PredictMixin:
    @classmethod
    def _add_predict(mcs, name: str, verbose_name: str, model_model_type: "Model", **kwargs) -> t.Dict[str, t.Any]:
        @resource_method("/predict/", methods=["POST"], name=f"{name}-predict")
        async def predict(
            self, model: model_model_type, data: flama.schemas.schemas.MLModelInput  # type: ignore[valid-type]
        ) -> flama.schemas.schemas.MLModelOutput:
            return {"output": model.predict(data["input"])}  # type: ignore[attr-defined]

        predict.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Generate a prediction.
            description:
                Generate a prediction using the model from this resource.
            responses:
                200:
                    description:
                        The prediction generated by the model.
        """

        return {"_predict": predict}


class ModelResource(BaseResource):
    component: "ModelComponent"
    model_path: t.Union[str, os.PathLike]


class ModelResourceType(ResourceType, InspectMixin, PredictMixin):
    METHODS = ("inspect", "predict")

    def __new__(mcs, name: str, bases: t.Tuple[type], namespace: t.Dict[str, t.Any]):
        """Resource metaclass for defining basic behavior for ML resources:
        * Create _meta attribute containing some metadata (model...).
        * Adds methods related to ML resource (inspect, predict...) listed in METHODS class attribute.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        """
        try:
            # Get model component
            component = mcs._get_model_component(bases, namespace)
            namespace["component"] = component
            namespace["model"] = component.model
        except AttributeError as e:
            raise ResourceAttributeError(str(e), name)

        metadata_namespace = {
            "component": component,
            "model": component.model,
            "model_type": component.get_model_type(),
        }
        if "_meta" in namespace:
            namespace["_meta"].namespaces["model"] = metadata_namespace
        else:
            namespace["_meta"] = data_structures.Metadata(namespaces={"model": metadata_namespace})

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def _get_model_component(mcs, bases: t.Sequence[t.Any], namespace: t.Dict[str, t.Any]) -> "ModelComponent":
        try:
            component: "ModelComponent" = mcs._get_attribute("component", bases, namespace, metadata_namespace="model")
            return component
        except AttributeError:
            ...

        try:
            with open(mcs._get_attribute("model_path", bases, namespace, metadata_namespace="model"), "rb") as f:
                return ModelComponentBuilder.loads(f.read())
        except AttributeError:
            ...

        raise AttributeError(ResourceAttributeError.MODEL_NOT_FOUND)
