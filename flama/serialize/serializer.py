import datetime
import os
import pathlib
import struct
import typing as t
import uuid
import warnings

from flama import exceptions, types
from flama.serialize.data_structures import Artifacts, CompressionFormat, ModelArtifact
from flama.serialize.model_serializers import ModelSerializer
from flama.serialize.protocols import Protocol

__all__ = ["Serializer", "dump", "load"]


class Serializer:
    """Main class for serializing and deserializing ML models in Flama's format.

    It handles the packaging of a model object and its metadata into a binary format, including a header for protocol
    and compression information, and delegating the core serialization to the appropriate protocol and model-specific
    serializers.
    """

    _header_format: t.Final[str] = "!I I Q"
    _header_size: t.Final[int] = struct.calcsize(_header_format)

    @t.overload
    @classmethod
    def dump(
        cls,
        m: t.Any,
        f: t.BinaryIO,
        /,
        *,
        protocol: types.ProtocolVersion = 1,
        compression: types.SerializationCompression = "zstd",
        model_id: str | uuid.UUID | None = None,
        timestamp: datetime.datetime | None = None,
        params: dict[str, t.Any] | None = None,
        metrics: dict[str, t.Any] | None = None,
        extra: dict[str, t.Any] | None = None,
        config: dict[str, t.Any] | None = None,
        artifacts: Artifacts | None = None,
        lib: types.Lib | None = None,
        **kwargs,
    ) -> None: ...
    @t.overload
    @classmethod
    def dump(
        cls,
        m: t.Any,
        /,
        *,
        path: str | os.PathLike | pathlib.Path,
        protocol: types.ProtocolVersion = 1,
        compression: types.SerializationCompression = "zstd",
        model_id: str | uuid.UUID | None = None,
        timestamp: datetime.datetime | None = None,
        params: dict[str, t.Any] | None = None,
        metrics: dict[str, t.Any] | None = None,
        extra: dict[str, t.Any] | None = None,
        config: dict[str, t.Any] | None = None,
        artifacts: Artifacts | None = None,
        lib: types.Lib | None = None,
        **kwargs,
    ) -> None: ...
    @t.overload
    @classmethod
    def dump(
        cls,
        m: str | os.PathLike | pathlib.Path,
        f: t.BinaryIO,
        /,
        *,
        lib: types.Lib,
        protocol: types.ProtocolVersion = 1,
        compression: types.SerializationCompression = "zstd",
        model_id: str | uuid.UUID | None = None,
        timestamp: datetime.datetime | None = None,
        params: dict[str, t.Any] | None = None,
        metrics: dict[str, t.Any] | None = None,
        extra: dict[str, t.Any] | None = None,
        config: dict[str, t.Any] | None = None,
        **kwargs,
    ) -> None: ...
    @t.overload
    @classmethod
    def dump(
        cls,
        m: str | os.PathLike | pathlib.Path,
        /,
        *,
        path: str | os.PathLike | pathlib.Path,
        lib: types.Lib,
        protocol: types.ProtocolVersion = 1,
        compression: types.SerializationCompression = "zstd",
        model_id: str | uuid.UUID | None = None,
        timestamp: datetime.datetime | None = None,
        params: dict[str, t.Any] | None = None,
        metrics: dict[str, t.Any] | None = None,
        extra: dict[str, t.Any] | None = None,
        config: dict[str, t.Any] | None = None,
        **kwargs,
    ) -> None: ...
    @classmethod
    def dump(
        cls,
        m: t.Any,
        f: t.BinaryIO | None = None,
        /,
        *,
        path: str | os.PathLike | pathlib.Path | None = None,
        protocol: types.ProtocolVersion = 1,
        compression: types.SerializationCompression = "zstd",
        model_id: str | uuid.UUID | None = None,
        timestamp: datetime.datetime | None = None,
        params: dict[str, t.Any] | None = None,
        metrics: dict[str, t.Any] | None = None,
        extra: dict[str, t.Any] | None = None,
        config: dict[str, t.Any] | None = None,
        artifacts: Artifacts | None = None,
        lib: types.Lib | None = None,
        **kwargs,
    ) -> None:
        """Serialize an ML model using Flama format to a writable binary stream.

        The body is streamed directly to *f* to avoid materialising the full archive in memory. A placeholder header is
        emitted first and patched with the body size once the protocol finishes writing.

        :param m: The ML model object, or a directory path containing model files.
        :param f: The bytes stream for dumping the model artifact.
        :param path: The file path where the model artifact will be stored.
        :param protocol: Serialization protocol version.
        :param compression: Compression format.
        :param model_id: The model ID.
        :param timestamp: The model timestamp.
        :param params: The model parameters.
        :param metrics: The model metrics.
        :param extra: The model extra data.
        :param config: Framework-specific configuration (e.g. ``{"task": "..."}`` for transformers).
        :param artifacts: The model artifacts.
        :param lib: The ML library name to use for serialization, required when *m* is a directory path.
        :param kwargs: Keyword arguments passed to library dump method.
        """
        if isinstance(m, str | os.PathLike | pathlib.Path):
            if lib is None:
                raise ValueError("Parameter 'lib' is required when 'm' is a directory path")
            m = pathlib.Path(m)

        if f is None and path is None:
            raise ValueError("Either a 'stream' or a 'path' needs to be provided")
        elif f is not None and path is not None:
            raise ValueError("Parameters 'stream' and 'path' are mutually exclusive")
        elif f is not None:
            managed_stream = False
        else:
            managed_stream = True
            f = pathlib.Path(str(path)).open("wb")

        p = Protocol.from_version(protocol)
        try:
            fmt = CompressionFormat[compression]
        except KeyError:
            raise ValueError(f"Wrong format '{compression}'")

        artifact = ModelArtifact.from_model(
            m,
            model_id=model_id,
            timestamp=timestamp,
            params=params,
            metrics=metrics,
            extra=extra,
            config=config,
            artifacts=artifacts,
            lib=lib,
        )

        try:
            header_pos = f.tell()
            f.write(b"\x00" * cls._header_size)

            body_size = p.dump(artifact, f, compression=fmt.name, **kwargs)

            end_pos = f.tell()
            f.seek(header_pos)
            f.write(struct.pack(cls._header_format, protocol, fmt.value, body_size))
            f.seek(end_pos)
        finally:
            if managed_stream:
                f.flush()
                f.close()

    @t.overload
    @classmethod
    def load(cls, f: t.BinaryIO, /, *, lib: types.Lib | None = None, **kwargs) -> ModelArtifact: ...
    @t.overload
    @classmethod
    def load(
        cls, /, *, path: str | os.PathLike | pathlib.Path, lib: types.Lib | None = None, **kwargs
    ) -> ModelArtifact: ...
    @classmethod
    def load(
        cls,
        f: t.BinaryIO | None = None,
        /,
        *,
        path: str | os.PathLike | pathlib.Path | None = None,
        lib: types.Lib | None = None,
        **kwargs,
    ) -> ModelArtifact:
        """Deserialize a ML model using Flama format from a bytes stream.

        :param f: The bytes stream for loading the model artifact.
        :param path: The file path where the model artifact is stored.
        :param lib: Optional ML library override for deserialization (defaults to the lib stored in metadata).
        :return: Model artifact.
        """
        if f is None and path is None:
            raise ValueError("Either a 'stream' or a 'path' needs to be provided")
        elif f is not None and path is not None:
            raise ValueError("Parameters 'stream' and 'path' are mutually exclusive")
        elif f is not None:
            managed_stream = False
        else:
            managed_stream = True
            f = pathlib.Path(str(path)).open("rb")

        try:
            protocol, compression, _body_size = struct.unpack(cls._header_format, f.read(cls._header_size))

            p = Protocol.from_version(protocol)
            try:
                fmt = CompressionFormat(compression)
            except ValueError:
                raise ValueError(f"Wrong format '{compression}'")
            artifact = p.load(f, compression=fmt.name, lib=lib)
        finally:
            if managed_stream:
                f.flush()
                f.close()

        if (
            serializer_version := ModelSerializer.from_lib(artifact.meta.framework.lib).version()
        ) != artifact.meta.framework.version:  # noqa
            warnings.warn(
                f"Model was built using {artifact.meta.framework.lib} '{artifact.meta.framework.version}' but "
                f"detected version '{serializer_version}' installed. This may cause unexpected behavior.",
                exceptions.FrameworkVersionWarning,
            )

        return artifact


dump = Serializer.dump
load = Serializer.load
