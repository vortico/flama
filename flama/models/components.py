import importlib
import os
import pathlib
import sys
import typing as t

from flama import types
from flama.injection import Component
from flama.models.base import BaseLLMModel, BaseMLModel, BaseModel
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


class _BaseLoader(t.Generic[M]):
    """Base builder for :class:`ModelComponent` instances backed by a serialized artifact.

    Concrete subclasses bind a narrow ``_registry`` mapping each supported lib to the
    Python module and class name that wraps the deserialized model. A registry miss raises
    :class:`ValueError`, which is the natural signal that an artifact's lib does not match
    the kind of resource using this builder (e.g. an ``sklearn`` artifact loaded through
    :class:`LLMModelComponentBuilder`).
    """

    _registry: t.ClassVar[dict[types.Lib, tuple[str, str]]]

    @classmethod
    def _get_model_class(cls, lib: types.Lib) -> type[M]:
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
    def load(cls, p: str | os.PathLike | pathlib.Path, /, *, lib: types.Lib | None = None) -> ModelArtifact:
        with pathlib.Path(str(p)).open("rb") as f:
            return Serializer.load(f, lib=lib)

    @classmethod
    def build(cls, m: ModelArtifact, /, *, lib: types.Lib) -> ModelComponent[M]:
        parent = cls._get_model_class(lib or m.meta.framework.lib)
        model_class = type(parent.__name__, (parent,), {})
        model_obj = model_class(m.model, m.meta, m.artifacts)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:
                return self.model

        return SpecificModelComponent(model_obj, artifact=m)


class _MLLoader(_BaseLoader[BaseMLModel]):
    """Builder for ML (non-LLM) model components.

    Accepts artifacts whose framework lib is one of :data:`flama.types.MLLib`.
    """

    _registry: t.ClassVar[dict[types.MLLib, tuple[str, str]]] = {
        "keras": ("flama.models.models.tensorflow", "Model"),
        "sklearn": ("flama.models.models.sklearn", "Model"),
        "tensorflow": ("flama.models.models.tensorflow", "Model"),
        "torch": ("flama.models.models.pytorch", "Model"),
        "transformers": ("flama.models.models.transformers", "Model"),
    }


class _LLMLoader(_BaseLoader[BaseLLMModel]):
    """Builder for LLM model components.

    Accepts artifacts whose framework lib is one of :data:`flama.types.LLMLib`.
    """

    _registry: t.ClassVar[dict[types.LLMLib, tuple[str, str]]] = {
        "vllm": ("flama.models.models.vllm", "MetalModel" if sys.platform == "darwin" else "CudaModel"),
    }


class ModelComponentBuilder:
    """Auto-dispatching builder accepting any supported framework lib.

    Combines the :data:`MLModelComponentBuilder._registry` and :data:`LLMModelComponentBuilder._registry`
    so a single ``load`` call works regardless of whether the artifact ships an ML or an LLM model.
    """

    @staticmethod
    @t.overload
    def build(p: str | os.PathLike | pathlib.Path, /, *, lib: types.LLMLib) -> ModelComponent[BaseLLMModel]: ...
    @staticmethod
    @t.overload
    def build(p: str | os.PathLike | pathlib.Path, /, *, lib: types.MLLib) -> ModelComponent[BaseMLModel]: ...
    @staticmethod
    @t.overload
    def build(
        p: str | os.PathLike | pathlib.Path, /, *, lib: types.LLMLib | types.MLLib | None = None
    ) -> ModelComponent[BaseLLMModel] | ModelComponent[BaseMLModel]: ...
    @staticmethod
    def build(
        p: str | os.PathLike | pathlib.Path, /, *, lib: types.LLMLib | types.MLLib | None = None
    ) -> ModelComponent[BaseLLMModel] | ModelComponent[BaseMLModel]:
        model = _BaseLoader.load(p, lib=lib)
        lib = lib or model.meta.framework.lib

        if types.is_llm_lib(lib):
            return _LLMLoader.build(model, lib=lib)
        else:
            return _MLLoader.build(model, lib=lib)
