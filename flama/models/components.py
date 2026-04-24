import importlib
import os
import pathlib
import sys
import typing as t

from flama import types
from flama.injection import Component
from flama.models.base import BaseModel
from flama.serialize.data_structures import ModelArtifact
from flama.serialize.serializer import Serializer

__all__ = ["ModelComponent", "ModelComponentBuilder"]

M = t.TypeVar("M", bound=BaseModel)


class ModelComponent(Component, t.Generic[M]):
    def __init__(self, model: M, artifact: ModelArtifact | None = None):
        self.model = model
        self._artifact = artifact

    def get_model_type(self) -> type[M]:
        return self.model.__class__

    def resolve(self) -> M:
        return self.model


class ModelComponentBuilder:
    _registry: t.Final[dict[types.MLLib, tuple[str, str]]] = {
        "keras": ("flama.models.models.tensorflow", "Model"),
        "sklearn": ("flama.models.models.sklearn", "Model"),
        "tensorflow": ("flama.models.models.tensorflow", "Model"),
        "torch": ("flama.models.models.pytorch", "Model"),
        "transformers": ("flama.models.models.transformers", "Model"),
        "vllm": ("flama.models.models.vllm", "MetalModel" if sys.platform == "darwin" else "CudaModel"),
    }

    @classmethod
    def _get_model_class(cls, lib: types.MLLib) -> type[BaseModel]:
        try:
            module_path, class_name = cls._registry[lib]
        except KeyError:  # pragma: no cover
            raise ValueError(f"Wrong lib '{lib}'")

        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:  # pragma: no cover
            raise ValueError(f"Module not found '{module_path}'")

        try:
            return getattr(module, class_name)
        except AttributeError:  # pragma: no cover
            raise ValueError(f"Class '{class_name}' not found in module '{module_path}'")

    @classmethod
    def load(cls, path: str | os.PathLike | pathlib.Path) -> "ModelComponent[BaseModel]":
        with pathlib.Path(str(path)).open("rb") as f:
            load_model = Serializer.load(f)

        parent = cls._get_model_class(load_model.meta.framework.lib)
        model_class = type(parent.__name__, (parent,), {})
        model_obj = model_class(load_model.model, load_model.meta, load_model.artifacts)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:
                return self.model

        return SpecificModelComponent(model_obj, artifact=load_model)
