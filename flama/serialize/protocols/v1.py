import json
import logging
import pathlib
import struct
import typing as t

from flama import types
from flama._core.json_encoder import encode_json
from flama.compression import compress, decompress, tar, untar
from flama.serialize.data_structures import Artifacts, Metadata, ModelArtifact, ModelDirectory
from flama.serialize.model_serializers import ModelSerializer
from flama.serialize.protocols.base import BaseProtocol

__all__ = ["Protocol"]

logger = logging.getLogger(__name__)


class _Artifact:
    _header_format: t.ClassVar[str] = "!I Q"
    _header_size: t.ClassVar[int] = struct.calcsize(_header_format)

    @classmethod
    def pack(cls, name: str, path: pathlib.Path, /, *, compression: types.SerializationCompression, **kwargs) -> bytes:
        with path.open("rb") as f:
            body = compress(f.read(), compression)

        return b"".join(
            (
                struct.pack(cls._header_format, len(name), len(body)),
                name.encode(),
                body,
            )
        )

    @classmethod
    def unpack(
        cls, b: bytes, /, *, compression: types.SerializationCompression, directory: pathlib.Path, **kwargs
    ) -> tuple[pathlib.Path, int]:
        name_size, content_size = struct.unpack(cls._header_format, b[: cls._header_size])
        offset = cls._header_size

        name = (b[offset : offset + name_size]).decode()
        offset += name_size

        content = b[offset : offset + content_size]

        path = directory / name
        with path.open("wb") as f:
            f.write(decompress(content, compression))

        return path, cls._header_size + name_size + content_size


class _Body:
    _header_format: t.ClassVar[str] = "!Q Q I Q"
    _header_size: t.ClassVar[int] = struct.calcsize(_header_format)

    @staticmethod
    def _pack_meta(meta: Metadata, *, compression: types.SerializationCompression) -> bytes:
        return compress(encode_json(meta.to_dict(), compact=True), compression)

    @staticmethod
    def _pack_artifacts(
        artifacts: Artifacts | None, *, compression: types.SerializationCompression
    ) -> tuple[int, bytes]:
        return len(artifacts) if artifacts else 0, b"".join(
            _Artifact.pack(name, pathlib.Path(str(path)), compression=compression)
            for name, path in (artifacts or {}).items()
        )

    @classmethod
    def pack(cls, m: ModelArtifact, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> int:
        """Stream-serialize a :class:`ModelArtifact` into *f*.

        Body header sizes are unknown until the model and artifacts are fully written, so a placeholder header is
        emitted first and patched once the sizes are known.

        :param m: Model artifact to serialise.
        :param f: A seekable writable binary stream.
        :param compression: Compression format name to apply to every section.
        :param kwargs: Forwarded to the framework-specific serializer (e.g. transformers ``save_pretrained`` kwargs).
        :return: Total number of body bytes written to *f* (header + sections).
        """
        body_start = f.tell()
        f.write(b"\x00" * cls._header_size)

        meta_bytes = cls._pack_meta(m.meta, compression=compression)
        f.write(meta_bytes)

        model_start = f.tell()
        if isinstance(m.model, pathlib.Path):
            tar(str(m.model), f, format=compression)
        else:
            model_bytes = compress(ModelSerializer.from_lib(m.meta.framework.lib).dump(m.model, **kwargs), compression)
            f.write(model_bytes)
        model_size = f.tell() - model_start

        artifacts_count, artifacts_bytes = cls._pack_artifacts(m.artifacts, compression=compression)
        f.write(artifacts_bytes)

        body_end = f.tell()
        f.seek(body_start)
        f.write(struct.pack(cls._header_format, len(meta_bytes), model_size, artifacts_count, len(artifacts_bytes)))
        f.seek(body_end)

        return body_end - body_start

    @staticmethod
    def _unpack_meta(b: bytes, *, compression: types.SerializationCompression) -> Metadata:
        return Metadata.from_dict(json.loads(decompress(b, compression).decode()))

    @staticmethod
    def _is_tar(data: bytes) -> bool:
        """Detect a POSIX tar archive by its ``ustar`` magic at offset 257."""
        return len(data) >= 263 and data[257:263] in (b"ustar\x00", b"ustar ")

    @staticmethod
    def _unpack_model(
        b: bytes,
        *,
        meta: Metadata,
        compression: types.SerializationCompression,
        directory: pathlib.Path,
        lib: types.Lib | None = None,
    ) -> t.Any:
        serializer = ModelSerializer.from_lib(lib or meta.framework.lib)

        load_kwargs: dict[str, t.Any] = {}
        if meta.framework.config:
            load_kwargs.update(meta.framework.config)

        data = decompress(b, compression)
        if _Body._is_tar(data):
            model_dir = directory / "model"
            model_dir.mkdir(exist_ok=True)
            untar(data, str(model_dir))
            return serializer.load(b"", model_dir=model_dir, **load_kwargs)

        return serializer.load(data, **load_kwargs)

    @staticmethod
    def _unpack_artifacts(
        b: bytes, *, count: int, compression: types.SerializationCompression, directory: pathlib.Path
    ) -> Artifacts:
        directory.mkdir(exist_ok=True)
        artifacts: Artifacts = {}
        offset = 0
        for _ in range(count):
            artifact, size = _Artifact.unpack(b[offset:], compression=compression, directory=directory)
            artifacts[artifact.name] = artifact
            offset += size
        return artifacts

    @classmethod
    def unpack(
        cls,
        f: t.BinaryIO,
        /,
        *,
        compression: types.SerializationCompression,
        lib: types.Lib | None = None,
        **kwargs,
    ) -> ModelArtifact:
        """Deserialize a :class:`ModelArtifact` from *f* positioned at the body header.

        Owns the temporary directory used during extraction: a fresh :class:`ModelDirectory` is
        created and bound on the returned artifact so its lifetime is tied to the artifact reference.

        :param f: A readable binary stream positioned at the body header.
        :param compression: Compression format used when packing.
        :param lib: Optional override for the framework library (defaults to ``meta.framework.lib``).
        :param kwargs: Forwarded to the framework-specific serializer.
        :return: Reconstructed :class:`ModelArtifact` with its :attr:`directory` field bound.
        """
        meta_size, model_size, artifacts_count, artifacts_size = struct.unpack(
            cls._header_format, f.read(cls._header_size)
        )

        directory = ModelDirectory()
        meta = cls._unpack_meta(f.read(meta_size), compression=compression)
        model = cls._unpack_model(
            f.read(model_size), meta=meta, compression=compression, directory=directory.directory, lib=lib
        )
        artifacts = cls._unpack_artifacts(
            f.read(artifacts_size),
            count=artifacts_count,
            compression=compression,
            directory=directory.directory / "artifacts",
        )

        return ModelArtifact(meta=meta, model=model, artifacts=artifacts, directory=directory)


class Protocol(BaseProtocol):
    """Version 1 of the Flama serialization protocol.

    Streams the body sections (metadata, model, artifacts) through a single seekable binary stream,
    using compression for every section and content-based detection (POSIX ``ustar`` magic) to
    distinguish raw model bytes from a tarred model directory.
    """

    def dump(self, m: ModelArtifact, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> int:
        """Stream-serialize *m* into *f*.

        :param m: Model artifact to serialise.
        :param f: A seekable writable binary stream.
        :param compression: Compression format name to apply to every section.
        :param kwargs: Forwarded to the framework-specific serializer.
        :return: Total number of body bytes written to *f*.
        """
        return _Body.pack(m, f, compression=compression, **kwargs)

    def load(
        self,
        f: t.BinaryIO,
        /,
        *,
        compression: types.SerializationCompression,
        lib: types.Lib | None = None,
        **kwargs,
    ) -> ModelArtifact:
        """Stream-deserialize a :class:`ModelArtifact` from *f*.

        :param f: Readable binary stream positioned at the body header.
        :param compression: Compression format used when packing.
        :param lib: Optional override for the framework library (defaults to ``meta.framework.lib``).
        :param kwargs: Forwarded to the framework-specific serializer.
        :return: Reconstructed :class:`ModelArtifact`. The returned artifact's :attr:`directory`
            field owns a temp directory kept alive for as long as the artifact is referenced.
        """
        artifact = _Body.unpack(f, compression=compression, lib=lib, **kwargs)

        logger.debug("Model '%s' extracted in directory '%s'", artifact, artifact.directory)

        return artifact
