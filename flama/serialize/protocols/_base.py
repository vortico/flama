import abc
import importlib
import pathlib
import typing as t

from flama import types
from flama.serialize.data_structures import Metadata, ModelArtifact
from flama.serialize.exceptions import UnsafeArtifactName

__all__ = ["BaseProtocol", "Protocol"]


class BaseProtocol(abc.ABC):
    """Base class for defining a serialization protocol for ML models."""

    lib: t.ClassVar[types.ModelLib]

    @staticmethod
    def artifact_name(name: str, /) -> str:
        """Validate a bundled artifact *name* against the wire format's naming contract.

        Only a single plain file name is accepted: absolute, nested, drive-qualified, traversal and
        empty names are all refused, so an artifact read from an untrusted ``.flm`` can never be
        materialised outside its extraction directory (``CWE-22``). Names are checked under both
        POSIX and Windows semantics, so an artifact written on one platform cannot escape on the
        other, and the relative directory names are rejected up front because :mod:`pathlib` keeps
        ``".."`` as an ordinary final component rather than normalising it away.

        Restricting to a single component also keeps
        :data:`~flama.serialize.data_structures.Artifacts` unambiguously keyed, as every protocol
        keys the unpacked mapping by file name.

        :param name: Artifact name as decoded from, or destined for, the wire format.
        :return: The validated name, unchanged.
        :raises UnsafeArtifactName: When *name* is not a plain file name.
        """
        if (
            not name
            or name in {".", ".."}
            or "\x00" in name
            or name != pathlib.PurePosixPath(name).name
            or name != pathlib.PureWindowsPath(name).name
        ):
            raise UnsafeArtifactName(name)

        return name

    @abc.abstractmethod
    def dump(self, m: ModelArtifact, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> int:
        """Stream-serialize a :class:`~flama.serialize.data_structures.ModelArtifact` into a writable binary file.

        :param m: The model artifact to serialize.
        :param f: A seekable writable binary stream that receives the serialized body.
        :param compression: The compression format name to use.
        :param kwargs: Additional keyword arguments for the serialization process.
        :return: Total number of body bytes written to *f*.
        """
        ...

    @abc.abstractmethod
    def load(self, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> ModelArtifact:
        """Deserialize a :class:`~flama.serialize.data_structures.ModelArtifact` from a readable binary file.

        :param f: A readable binary stream positioned at the start of the serialized body.
        :param compression: The compression format name used on the body.
        :param kwargs: Additional keyword arguments for the deserialization process.
        :return: The deserialized model artifact.
        """
        ...

    @abc.abstractmethod
    def meta(self, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> Metadata:
        """Read only the :class:`~flama.serialize.data_structures.Metadata` section from a readable binary file.

        Mirrors :meth:`load`'s framing but stops after decoding the metadata frame, leaving the
        model body and artifacts untouched. Intended for cheap header-only inspection (lib
        auto-detection, lazy registration) where the model itself is not yet needed.

        :param f: A readable binary stream positioned at the start of the serialized body.
        :param compression: The compression format name used on the body.
        :param kwargs: Additional keyword arguments forwarded to the protocol implementation.
        :return: The model metadata.
        """
        ...

    @abc.abstractmethod
    def manifest(self, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> tuple[str, ...]:
        """Read the bundled artifact names from a serialized model.

        Walks the per-artifact headers to collect names without decompressing or extracting
        their contents — and without decoding the metadata. Cheapest possible introspection
        for callers that only need to know *what* is packaged.

        :param f: A readable binary stream positioned at the start of the serialized body.
        :param compression: The compression format name used on the body.
        :param kwargs: Additional keyword arguments forwarded to the protocol implementation.
        :return: The names of bundled artifacts, in packed order.
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
