import os
import typing as t

import flama.schemas
from flama import types
from flama.models.components import ModelComponentBuilder
from flama.resources import BaseResource, data_structures
from flama.resources.exceptions import ResourceAttributeError
from flama.resources.resource import ResourceType
from flama.resources.routing import resource_method

if t.TYPE_CHECKING:
    from flama.models.base import Model
    from flama.models.components import ModelComponent

__all__ = ["ModelResource", "InspectMixin", "PredictMixin", "ModelResourceType"]


class InspectMixin:
    @classmethod
    def _add_inspect(
        cls, name: str, verbose_name: str, model_model_type: t.Type["Model"], **kwargs
    ) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["GET"], name="inspect")
        async def inspect(self, model: model_model_type):  # type: ignore[valid-type]
            return model.inspect()  # type: ignore[attr-defined]

        inspect.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Retrieve the model
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
    def _add_predict(
        cls, name: str, verbose_name: str, model_model_type: t.Type["Model"], **kwargs
    ) -> t.Dict[str, t.Any]:
        @resource_method("/predict/", methods=["POST"], name="predict")
        async def predict(
            self,
            model: model_model_type,  # type: ignore[valid-type]
            data: types.Schema[flama.schemas.schemas.MLModelInput],  # type: ignore[type-arg]
        ) -> types.Schema[flama.schemas.schemas.MLModelOutput]:  # type: ignore[type-arg]
            return types.Schema({"output": model.predict(data["input"])})  # type: ignore[attr-defined]

        predict.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Generate a prediction
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

        namespace.setdefault("_meta", data_structures.Metadata()).namespaces["model"] = {
            "component": component,
            "model": component.model,
            "model_type": component.get_model_type(),
        }

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def _get_model_component(cls, bases: t.Sequence[t.Any], namespace: t.Dict[str, t.Any]) -> "ModelComponent":
        try:
            component: "ModelComponent" = cls._get_attribute("component", bases, namespace, metadata_namespace="model")
            return component
        except AttributeError:
            ...

        try:
            return ModelComponentBuilder.load(
                cls._get_attribute("model_path", bases, namespace, metadata_namespace="model")
            )
        except AttributeError:
            ...

        raise AttributeError(ResourceAttributeError.MODEL_NOT_FOUND)
