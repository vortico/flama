import abc
import importlib
import typing as t

from flama import types
from flama.serialize.compression import Compression
from flama.serialize.data_structures import ModelArtifact

__all__ = ["BaseProtocol", "Protocol"]


class BaseProtocol(abc.ABC):
    """Base class for defining a serialization protocol for ML models."""

    lib: t.ClassVar[types.MLLib]

    @abc.abstractmethod
    def dump(self, m: ModelArtifact, /, *, compression: Compression, **kwargs) -> bytes:
        """Serializes a :class:`~flama.serialize.data_structures.ModelArtifact` into bytes according to the protocol.

        :param m: The model artifact to serialize.
        :param compression: The compression algorithm to use for the resulting bytes.
        :param kwargs: Additional keyword arguments for the serialization process.
        :return: The serialized model artifact as bytes.
        """
        ...

    @abc.abstractmethod
    def load(self, b: bytes, /, *, compression: Compression, **kwargs) -> ModelArtifact:
        """Deserializes bytes into a :class:`~flama.serialize.data_structures.ModelArtifact` according to the protocol.

        :param b: The bytes representing the serialized model artifact.
        :param compression: The compression algorithm used on the bytes.
        :param kwargs: Additional keyword arguments for the deserialization process.
        :return: The deserialized model artifact.
        """
        ...


class Protocol:
    """Factory class for obtaining a specific serialization protocol implementation based on the protocol version.

    This class provides a way to dynamically load the appropriate protocol class from version-specific modules.
    """

    _module_name: t.Final[str] = "flama.serialize.protocols.v{}"
    _class_name: t.Final[str] = "Protocol"

    @classmethod
    def from_version(cls, version: types.ProtocolVersion, /) -> BaseProtocol:
        """Loads and instantiates the concrete protocol class for the given version.

        The protocol class is expected to be named ``Protocol`` and located in a module
        named ``flama.serialize.protocols.v<version>``.

        :param version: The protocol version to load (e.g., ``"1"``).
        :raises ValueError: If the protocol version is wrong, the module is not found, or the class is not found in
        the module.
        :return: An instance of the concrete protocol class implementing :class:`BaseProtocol`.
        """
        try:
            return getattr(importlib.import_module(cls._module_name.format(version)), cls._class_name)()
        except KeyError:  # pragma: no cover
            raise ValueError(f"Wrong protocol version '{version}'")
        except ModuleNotFoundError:  # pragma: no cover
            raise ValueError(f"Module not found '{cls._module_name.format(version)}'")
        except AttributeError:  # pragma: no cover
            raise ValueError(f"Class '{cls._class_name}' not found in module '{cls._module_name.format(version)}'")
