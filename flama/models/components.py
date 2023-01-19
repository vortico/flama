import importlib
import typing as t

from flama.injection import Component
from flama.models.base import Model
from flama.serialize import loads
from flama.serialize.types import Framework

__all__ = ["ModelComponent", "ModelComponentBuilder"]


class ModelComponent(Component):
    def __init__(self, model):
        self.model = model

    def get_model_type(self) -> t.Type[Model]:
        return self.model.__class__  # type: ignore[no-any-return]


class ModelComponentBuilder:
    @classmethod
    def _get_model_class(cls, framework: Framework) -> t.Type[Model]:
        try:
            module, class_name = {
                Framework.torch: ("pytorch", "PyTorchModel"),
                Framework.sklearn: ("sklearn", "SKLearnModel"),
                Framework.tensorflow: ("tensorflow", "TensorFlowModel"),
                Framework.keras: ("tensorflow", "TensorFlowModel"),
            }[framework]
        except KeyError:  # pragma: no cover
            raise ValueError("Wrong framework")

        model_class: t.Type[Model] = getattr(importlib.import_module(f"flama.models.models.{module}"), class_name)
        return model_class

    @classmethod
    def loads(cls, data: bytes) -> ModelComponent:
        load_model = loads(data)
        parent = cls._get_model_class(load_model.meta.framework.lib)
        model_class = type(parent.__name__, (parent,), {})
        model_obj = model_class(load_model.model, load_model.meta)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:  # type: ignore[valid-type]
                return self.model  # type: ignore[no-any-return]

        return SpecificModelComponent(model_obj)
