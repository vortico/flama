import importlib
import os
import pathlib
import typing as t

from flama import types
from flama.injection import Component
from flama.models.base import BaseModel
from flama.serialize.serializer import Serializer

__all__ = ["ModelComponent", "ModelComponentBuilder"]


class ModelComponent(Component):
    def __init__(self, model):
        self.model = model

    def get_model_type(self) -> type[BaseModel]:
        return self.model.__class__  # type: ignore[no-any-return]


class ModelComponentBuilder:
    _module_name: t.Final[str] = "flama.models.models.{}"
    _class_name: t.Final[str] = "Model"
    _modules: t.Final[dict[types.MLLib, str]] = {
        "keras": "tensorflow",
        "sklearn": "sklearn",
        "tensorflow": "tensorflow",
        "torch": "pytorch",
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
    def load(cls, path: str | os.PathLike | pathlib.Path) -> ModelComponent:
        with pathlib.Path(str(path)).open("rb") as f:
            load_model = Serializer.load(f)

        parent = cls._get_model_class(load_model.meta.framework.lib)
        model_class = type(parent.__name__, (parent,), {})
        model_obj = model_class(load_model.model, load_model.meta, load_model.artifacts)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:  # type: ignore[valid-type]
                return self.model  # type: ignore[no-any-return]

        return SpecificModelComponent(model_obj)
