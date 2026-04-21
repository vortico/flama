import importlib
import os
import pathlib
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
    _module_name: t.Final[str] = "flama.models.models.{}"
    _class_name: t.Final[str] = "Model"
    _modules: t.Final[dict[types.MLLib, str]] = {
        "keras": "tensorflow",
        "sklearn": "sklearn",
        "tensorflow": "tensorflow",
        "torch": "pytorch",
        "transformers": "transformers",
        "vllm": "vllm",
    }

    @classmethod
    def _get_model_class(cls, lib: types.MLLib) -> type[BaseModel]:
        try:
            return getattr(importlib.import_module(cls._module_name.format(cls._modules[lib])), cls._class_name)
        except KeyError:  # pragma: no cover
            raise ValueError(f"Wrong lib '{lib}'")
        except ModuleNotFoundError:  # pragma: no cover
            raise ValueError(f"Module not found '{cls._module_name.format(cls._modules[lib])}'")
        except AttributeError:  # pragma: no cover
            raise ValueError(
                f"Class '{cls._class_name}' not found in module '{cls._module_name.format(cls._modules[lib])}'"
            )

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
