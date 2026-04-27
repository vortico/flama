import abc
import importlib
import inspect
import sys
import typing as t

from flama import types

__all__ = ["BaseModelSerializer", "ModelSerializer"]


class BaseModelSerializer(abc.ABC):
    """Base class for defining a model-specific serializer for ML models.

    This abstract class defines the interface for concrete serializers tailored to specific machine learning
    frameworks (e.g., scikit-learn, TensorFlow).

    It includes methods for serializing a model object to bytes, deserializing
    bytes back to a model object, extracting model metadata, and getting
    the serializer version.
    """

    lib: t.ClassVar[types.Lib]

    @abc.abstractmethod
    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        """Serializes a model object into bytes specific to the ML library.

        :param obj: The model object to serialize.
        :param kwargs: Additional keyword arguments for the serialization process.
        :return: The serialized model as bytes.
        """
        ...

    @abc.abstractmethod
    def load(self, model: bytes, /, **kwargs) -> t.Any:
        """Deserializes bytes back into a model object specific to the ML library.

        :param model: The bytes representing the serialized model.
        :param kwargs: Additional keyword arguments for the deserialization process.
        :return: The deserialized model object.
        """
        ...

    @abc.abstractmethod
    def info(self, model: t.Any, /) -> types.JSONSchema | None:
        """Extracts and returns metadata about the model, typically as a JSON Schema.

        :param model: The model object to inspect.
        :return: A JSONSchema object containing model metadata, or ``None`` if no metadata is available.
        """
        ...

    @abc.abstractmethod
    def version(self) -> str:
        """Returns the version of the serialization protocol used by this serializer.

        :return: The version string.
        """
        ...


class ModelSerializer:
    """Factory class for obtaining the appropriate model-specific serializer.

    This class provides methods to dynamically load a concrete :class:`BaseModelSerializer`
    implementation based on the ML library name or by inspecting a model object.
    """

    _registry: t.Final[dict[types.Lib, tuple[str, str]]] = {
        "keras": ("flama.serialize.model_serializers.tensorflow", "ModelSerializer"),
        "sklearn": ("flama.serialize.model_serializers.sklearn", "ModelSerializer"),
        "tensorflow": ("flama.serialize.model_serializers.tensorflow", "ModelSerializer"),
        "torch": ("flama.serialize.model_serializers.pytorch", "ModelSerializer"),
        "transformers": ("flama.serialize.model_serializers.transformers", "ModelSerializer"),
        "vllm": (
            "flama.serialize.model_serializers.vllm",
            "MetalModelSerializer" if sys.platform == "darwin" else "CudaModelSerializer",
        ),
    }

    @classmethod
    def from_lib(cls, lib: types.Lib, /) -> BaseModelSerializer:
        """Loads and instantiates the concrete model serializer class for the given ML library.

        :param lib: The name of the machine learning library (e.g., ``"sklearn"``, ``"tensorflow"``).
        :return: An instance of the concrete model serializer class implementing :class:`BaseModelSerializer`.
        :raises ValueError: If the library name is unknown, the corresponding module is not found,
                            or the class is not found in the module.
        """
        try:
            module_path, class_name = cls._registry[lib]
        except KeyError:  # pragma: no cover
            raise ValueError(f"Wrong lib '{lib}'")

        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:  # pragma: no cover
            raise ValueError(f"Module not found '{module_path}'")

        try:
            return getattr(module, class_name)()
        except AttributeError:  # pragma: no cover
            raise ValueError(f"Class '{class_name}' not found in module '{module_path}'")

    @classmethod
    def from_model(cls, model: t.Any, /) -> BaseModelSerializer:
        """Determines the appropriate model serializer by inspecting the given model object's module and class
        hierarchy, and returns an instance of that serializer.

        :param model: The ML model object to inspect.
        :return: An instance of the concrete model serializer class for the detected framework.
        :raises ValueError: If the framework of the model cannot be determined.
        """
        inspect_objs = [model]

        try:
            inspect_objs += model.__class__.__mro__
        except AttributeError:  # pragma: no cover
            ...

        for obj in inspect_objs:
            try:
                module = inspect.getmodule(obj)
                if module is None:
                    continue
                return cls.from_lib(t.cast(types.Lib, module.__name__.split(".", 1)[0]))
            except (ValueError, AttributeError):
                ...
        else:  # pragma: no cover
            raise ValueError("Unknown model framework")
