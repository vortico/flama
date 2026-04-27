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

__all__ = ["ModelComponent", "MLModelComponentBuilder", "LLMModelComponentBuilder"]

M = t.TypeVar("M", bound=BaseModel)


class ModelComponent(Component, t.Generic[M]):
    def __init__(self, model: M, artifact: ModelArtifact | None = None):
        self.model = model
        self._artifact = artifact

    def get_model_type(self) -> type[M]:
        return self.model.__class__

    def resolve(self) -> M:
        return self.model


class _ModelComponentBuilder:
    """Base builder for :class:`ModelComponent` instances backed by a serialized artifact.

    Concrete subclasses bind a narrow ``_registry`` mapping each supported lib to the
    Python module and class name that wraps the deserialized model. A registry miss raises
    :class:`ValueError`, which is the natural signal that an artifact's lib does not match
    the kind of resource using this builder (e.g. an ``sklearn`` artifact loaded through
    :class:`LLMModelComponentBuilder`).
    """

    _registry: t.ClassVar[dict[types.Lib, tuple[str, str]]]

    @classmethod
    def _get_model_class(cls, lib: types.Lib) -> type[BaseModel]:
        try:
            module_path, class_name = cls._registry[lib]
        except KeyError:
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
    def load(
        cls, path: str | os.PathLike | pathlib.Path, *, lib: types.Lib | None = None
    ) -> "ModelComponent[BaseModel]":
        """Load a serialized ``.flm`` artifact and wrap it in a :class:`ModelComponent`.

        :param path: Path to the ``.flm`` artifact.
        :param lib: Optional override for the lib stored in metadata. Forces both the deserializer
            and the model component class to use this lib.
        :raises ValueError: If the resolved lib is not registered on this builder.
        :return: A :class:`ModelComponent` wrapping the deserialized model.
        """
        with pathlib.Path(str(path)).open("rb") as f:
            load_model = Serializer.load(f, lib=lib)

        parent = cls._get_model_class(lib or load_model.meta.framework.lib)
        model_class = type(parent.__name__, (parent,), {})
        model_obj = model_class(load_model.model, load_model.meta, load_model.artifacts)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:
                return self.model

        return SpecificModelComponent(model_obj, artifact=load_model)


class MLModelComponentBuilder(_ModelComponentBuilder):
    """Builder for ML (non-LLM) model components.

    Accepts artifacts whose framework lib is one of :data:`flama.types.MLLib`.
    """

    _registry: t.ClassVar[dict[types.Lib, tuple[str, str]]] = {
        "keras": ("flama.models.models.tensorflow", "Model"),
        "sklearn": ("flama.models.models.sklearn", "Model"),
        "tensorflow": ("flama.models.models.tensorflow", "Model"),
        "torch": ("flama.models.models.pytorch", "Model"),
        "transformers": ("flama.models.models.transformers", "Model"),
    }


class LLMModelComponentBuilder(_ModelComponentBuilder):
    """Builder for LLM model components.

    Accepts artifacts whose framework lib is one of :data:`flama.types.LLMLib`.
    """

    _registry: t.ClassVar[dict[types.Lib, tuple[str, str]]] = {
        "vllm": ("flama.models.models.vllm", "MetalModel" if sys.platform == "darwin" else "CudaModel"),
    }
