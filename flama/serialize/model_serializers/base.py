import abc
import importlib
import inspect
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

    lib: t.ClassVar[types.MLLib]

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

    _module_name: t.Final[str] = "flama.serialize.model_serializers.{}"
    _class_name: t.Final[str] = "ModelSerializer"
    _modules: t.Final[dict[types.MLLib, str]] = {
        "keras": "tensorflow",
        "sklearn": "sklearn",
        "tensorflow": "tensorflow",
        "torch": "pytorch",
    }

    @classmethod
    def from_lib(cls, lib: types.MLLib, /) -> BaseModelSerializer:
        """Loads and instantiates the concrete model serializer class for the given ML library.

        The serializer class is expected to be named ``ModelSerializer`` and located in a library-specific module
        (e.g., ``flama.serialize.model_serializers.sklearn``).

        :param lib: The name of the machine learning library (e.g., ``"sklearn"``, ``"tensorflow"``).
        :return: An instance of the concrete model serializer class implementing :class:`BaseModelSerializer`.
        :raises ValueError: If the library name is unknown, the corresponding module is not found,
                            or the class is not found in the module.
        """
        try:
            return getattr(importlib.import_module(cls._module_name.format(cls._modules[lib])), cls._class_name)()
        except KeyError:  # pragma: no cover
            raise ValueError(f"Wrong lib '{lib}'")
        except ModuleNotFoundError:  # pragma: no cover
            raise ValueError(f"Module not found '{cls._module_name.format(cls._modules[lib])}'")
        except AttributeError:  # pragma: no cover
            raise ValueError(
                f"Class '{cls._class_name}' not found in module '{cls._module_name.format(cls._modules[lib])}'"
            )

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
                return cls.from_lib(inspect.getmodule(obj).__name__.split(".", 1)[0])  # type: ignore[union-attr]
            except (ValueError, AttributeError):
                ...
        else:  # pragma: no cover
            raise ValueError("Unknown model framework")
