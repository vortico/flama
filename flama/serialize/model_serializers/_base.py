import abc
import importlib
import inspect
import pathlib
import typing as t

from flama import types

if t.TYPE_CHECKING:
    from flama.serialize.data_structures import ModelCapabilities

__all__ = ["BaseModelSerializer", "ModelSerializer"]


class BaseModelSerializer(abc.ABC):
    """Base class for defining a model-specific serializer for ML models.

    This abstract class defines the interface for concrete serializers tailored to specific machine learning
    frameworks (e.g., scikit-learn, TensorFlow).

    It includes methods for serializing a model object to bytes, deserializing the wire-level source
    back to a model object, extracting model metadata, and getting the serializer version.

    The :meth:`load` contract is unified across families: implementations accept either raw ``bytes``
    (binary model section) or a :class:`pathlib.Path` (extracted bundle directory). Concrete
    serializers narrow the accepted variant via runtime ``isinstance`` checks; bytes-only frameworks
    (sklearn/pytorch/tensorflow) reject paths and bundle-only frameworks (transformers) reject
    bytes. Wire-level discrimination between the two kinds lives in the
    kind byte on v2 dumps (see :data:`~flama.types.SerializationModelKind`), so the serializer never needs
    to carry a class-level ``from_directory`` flag.

    The :data:`~flama.types.ModelFamily` discriminator is persisted directly on
    :class:`~flama.serialize.data_structures.FrameworkInfo` at dump time, so serializers stay
    family-agnostic; the :class:`~flama.serialize.data_structures.ModelCapabilities` subclass
    returned from :meth:`detect_capabilities` carries its own ``kind`` discriminator.
    """

    lib: t.ClassVar[types.ModelLib]

    @abc.abstractmethod
    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        """Serializes a model object into bytes specific to the ML library.

        :param obj: The model object to serialize.
        :param kwargs: Additional keyword arguments for the serialization process.
        :return: The serialized model as bytes.
        """
        ...

    @abc.abstractmethod
    def load(self, source: bytes | pathlib.Path, /, **kwargs) -> t.Any:
        """Deserialize a wire-level model source into a live framework object.

        ``source`` is either raw ``bytes`` (binary section payload) or a :class:`pathlib.Path` to an
        extracted bundle directory. Concrete serializers accept exactly one variant and raise
        :class:`TypeError` (or :class:`ValueError`) when handed the other.

        :param source: Serialized model bytes or path to an extracted model bundle directory.
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

    @abc.abstractmethod
    def detect_capabilities(self, model: t.Any, /) -> "ModelCapabilities | None":
        """Detect the modal capabilities of *model* for embedding into the artifact manifest.

        Each concrete serializer owns its detection logic and returns the family-appropriate
        :class:`~flama.serialize.data_structures.ModelCapabilities` subclass
        (:class:`~flama.serialize.data_structures.MLModelCapabilities` for traditional ML,
        :class:`~flama.serialize.data_structures.LLMModelCapabilities` for LLMs). Returning
        :data:`None` signals "capabilities cannot be determined for this artifact"; downstream
        load paths that depend on capabilities (notably MLX/vLLM dispatch) raise
        :class:`~flama.serialize.exceptions.UnknownModelCapabilities` rather than guessing.

        :param model: Model object, pipeline, or extracted directory being serialised or loaded.
        :return: Detected capabilities, or :data:`None` when they cannot be resolved.
        """
        ...


class ModelSerializer:
    """Factory class for obtaining the appropriate model-specific serializer.

    This class provides methods to dynamically load a concrete :class:`BaseModelSerializer`
    implementation based on the ML library name or by inspecting a model object.
    """

    _registry: t.Final[dict[types.ModelLib, tuple[str, str]]] = {
        "keras": ("flama.serialize.model_serializers.tensorflow", "ModelSerializer"),
        "sklearn": ("flama.serialize.model_serializers.sklearn", "ModelSerializer"),
        "tensorflow": ("flama.serialize.model_serializers.tensorflow", "ModelSerializer"),
        "torch": ("flama.serialize.model_serializers.pytorch", "ModelSerializer"),
        "transformers": ("flama.serialize.model_serializers.transformers", "ModelSerializer"),
    }

    @classmethod
    def from_lib(cls, lib: types.ModelLib, /) -> BaseModelSerializer:
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
                return cls.from_lib(t.cast(types.ModelLib, module.__name__.split(".", 1)[0]))
            except (ValueError, AttributeError):
                ...
        else:  # pragma: no cover
            raise ValueError("Unknown model framework")
