import importlib
import os

from flama.injection import Component
from flama.models.base import Model
from flama.serialize import load
from flama.serialize.types import Framework

__all__ = ["ModelComponent", "ModelComponentBuilder"]


class ModelComponent(Component):
    def __init__(self, model):
        self.model = model

    def get_model_type(self) -> type[Model]:
        return self.model.__class__  # type: ignore[no-any-return]


class ModelComponentBuilder:
    @classmethod
    def _get_model_class(cls, framework: Framework) -> type[Model]:
        try:
            module, class_name = {
                Framework.torch: ("pytorch", "PyTorchModel"),
                Framework.sklearn: ("sklearn", "SKLearnModel"),
                Framework.tensorflow: ("tensorflow", "TensorFlowModel"),
                Framework.keras: ("tensorflow", "TensorFlowModel"),
            }[framework]
        except KeyError:  # pragma: no cover
            raise ValueError("Wrong framework")

        model_class: type[Model] = getattr(importlib.import_module(f"flama.models.models.{module}"), class_name)
        return model_class

    @classmethod
    def load(cls, path: str | os.PathLike) -> ModelComponent:
        load_model = load(path)
        parent = cls._get_model_class(load_model.meta.framework.lib)
        model_class = type(parent.__name__, (parent,), {})
        model_obj = model_class(load_model.model, load_model.meta, load_model.artifacts)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:  # type: ignore[valid-type]
                return self.model  # type: ignore[no-any-return]

        return SpecificModelComponent(model_obj)
