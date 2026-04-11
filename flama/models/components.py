import datetime
import importlib
import os
import pathlib
import typing as t
import uuid

from flama import types
from flama.injection import Component
from flama.models.base import BaseModel
from flama.serialize.data_structures import FrameworkInfo, Metadata, ModelInfo
from flama.serialize.model_serializers import ModelSerializer
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
        "transformers": "transformers",
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
    def _build_component(cls, lib: types.MLLib, model_obj: t.Any, meta: Metadata, artifacts: t.Any) -> "ModelComponent":
        parent = cls._get_model_class(lib)
        model_class = type(parent.__name__, (parent,), {})
        model_instance = model_class(model_obj, meta, artifacts)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:  # type: ignore[valid-type]
                return self.model  # type: ignore[no-any-return]

        return SpecificModelComponent(model_instance)

    @classmethod
    def load(cls, path: str | os.PathLike | pathlib.Path) -> "ModelComponent":
        path_ = pathlib.Path(str(path))

        if path_.suffix or path_.exists():
            return cls._load_from_file(path_)

        return cls._load_from_id(str(path))

    @classmethod
    def _load_from_file(cls, path: pathlib.Path) -> "ModelComponent":
        with path.open("rb") as f:
            load_model = Serializer.load(f)

        return cls._build_component(
            load_model.meta.framework.lib, load_model.model, load_model.meta, load_model.artifacts
        )

    @classmethod
    def _load_from_id(cls, model_id: str) -> "ModelComponent":
        lib: types.MLLib = "transformers"
        serializer = ModelSerializer.from_lib(lib)
        model_obj = serializer.load_from_id(model_id)

        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime.now(),
            framework=FrameworkInfo(lib=lib, version=serializer.version()),
            model=ModelInfo(obj=model_id, info=serializer.info(model_obj)),
        )

        return cls._build_component(lib, model_obj, meta, None)
