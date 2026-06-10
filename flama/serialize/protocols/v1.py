"""Version 1 of the Flama serialization protocol — binary-only legacy reader/writer.

The body carries fixed-format section frame sizes (meta, model, artifacts) in a single header and the sections
themselves; per-section compression is implicit (every section uses the file-level codec), there is no model-kind
discriminator, and only :data:`bytes` model sources are accepted at dump time. Directory bundles require
:class:`flama.serialize.protocols.v2.Protocol`.

Wire layout::

    body header                28 b
        meta_size              Q
        model_size             Q
        artifacts_count        I
        artifacts_size         Q
    meta section
        payload                ... compressed JSON bytes
    model section
        payload                ... compressed raw bytes
    artifacts section
        artifact * count
            name_size          I
            content_size       Q
            name               utf-8 bytes
            content            compressed payload bytes

v1 stays available so older ``.flm`` files keep loading; the
:meth:`~flama.serialize.data_structures.FrameworkInfo.from_dict` default of ``"ml"`` covers the schema delta.
Unrepresentable shapes (directory sources) raise :class:`~flama.serialize.exceptions.UnsupportedProtocol` at dump time.
"""

import json
import logging
import pathlib
import struct
import typing as t

from flama import types
from flama._core.compression import compress, decompress
from flama._core.json_encoder import encode_json
from flama.serialize.data_structures import Artifacts, Metadata, ModelArtifact, ModelDirectory
from flama.serialize.exceptions import UnsupportedProtocol
from flama.serialize.model_serializers import ModelSerializer
from flama.serialize.protocols._base import BaseProtocol

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

    @staticmethod
    def _ensure_supported(m: ModelArtifact) -> None:
        """Verify *m* fits v1's binary-only contract.

        v1 mirrors master's writer: framework-serialized binary models with a bytes source (or a
        live model object the serializer can turn into bytes). A :class:`pathlib.Path` source means
        the artifact is a directory bundle, which has no representation in the v1 wire format —
        bundles require :class:`flama.serialize.protocols.v2.Protocol`, which carries an explicit
        kind byte (see :data:`~flama.types.SerializationModelKind`).

        :raises UnsupportedProtocol: If *m*'s shape is not representable in v1.
        """
        if isinstance(m.source, pathlib.Path):
            raise UnsupportedProtocol(protocol=1, reason="bundle source (directory path)")

    @classmethod
    def pack(cls, m: ModelArtifact, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> int:
        """Stream-serialize *m* into *f*.

        Binary-only writer: :class:`pathlib.Path` sources (directory bundles) are refused via
        :meth:`_ensure_supported` — those shapes require
        :class:`flama.serialize.protocols.v2.Protocol`. Body header sizes are unknown until each
        section is fully written; a placeholder header is emitted first and patched once the sizes
        are known.

        :param m: Model artifact to serialise.
        :param f: A seekable writable binary stream.
        :param compression: Compression format name applied uniformly to every section.
        :param kwargs: Forwarded to the framework-specific serializer.
        :return: Total number of body bytes written to *f*.
        :raises UnsupportedProtocol: If *m*'s shape is not representable in v1.
        """
        cls._ensure_supported(m)

        body_start = f.tell()
        f.write(b"\x00" * cls._header_size)

        meta_bytes = cls._pack_meta(m.meta, compression=compression)
        f.write(meta_bytes)

        model_start = f.tell()
        if isinstance(m.source, bytes):
            f.write(compress(m.source, compression))
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
    def _unpack_model(f: t.BinaryIO, *, size: int, compression: types.SerializationCompression) -> bytes:
        """Read and decompress the binary model section of *f*.

        v1 carries only binary model sections (see :meth:`_ensure_supported`); the wire format
        has no kind discriminator, so the decoder always returns decompressed bytes.
        Materialisation into a live framework object is deferred to
        :attr:`flama.serialize.data_structures.ModelArtifact.model`, keeping the protocol
        family-agnostic.
        """
        return decompress(f.read(size), compression)

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
        **kwargs,
    ) -> ModelArtifact:
        """Deserialize a :class:`ModelArtifact` from *f* positioned at the body header.

        Owns the temporary directory used during extraction: a fresh :class:`ModelDirectory` is
        created and bound on the returned artifact so its lifetime is tied to the artifact reference.

        :param f: A readable binary stream positioned at the body header.
        :param compression: Compression format used when packing (applied uniformly to every section).
        :return: Reconstructed :class:`ModelArtifact` with its :attr:`directory` field bound and its
            :attr:`source` set to the decompressed model bytes.
        """
        meta_size, model_size, artifacts_count, artifacts_size = struct.unpack(
            cls._header_format, f.read(cls._header_size)
        )

        directory = ModelDirectory()
        meta = cls._unpack_meta(f.read(meta_size), compression=compression)
        source = cls._unpack_model(f, size=model_size, compression=compression)
        artifacts = cls._unpack_artifacts(
            f.read(artifacts_size),
            count=artifacts_count,
            compression=compression,
            directory=directory.directory / "artifacts",
        )

        return ModelArtifact(meta=meta, source=source, artifacts=artifacts, directory=directory)

    @classmethod
    def unpack_meta(cls, f: t.BinaryIO, /, *, compression: types.SerializationCompression) -> Metadata:
        """Read only the :class:`Metadata` section from *f* positioned at the body header.

        Reads the body header to determine the metadata frame size, decodes that frame, and stops
        without touching the model or artifact sections. The stream is left positioned past the
        metadata frame.
        """
        meta_size, _model_size, _artifacts_count, _artifacts_size = struct.unpack(
            cls._header_format, f.read(cls._header_size)
        )
        return cls._unpack_meta(f.read(meta_size), compression=compression)

    @classmethod
    def unpack_manifest(cls, f: t.BinaryIO, /, *, compression: types.SerializationCompression) -> tuple[str, ...]:
        """Read the bundled artifact names from *f*.

        Walks the per-artifact ``(name_size, content_size)`` headers, reads the names, and seeks
        past the content bytes — never decompressing or decoding the metadata, model, or artifact
        contents. Cheapest possible introspection.
        """
        meta_size, model_size, artifacts_count, _artifacts_size = struct.unpack(
            cls._header_format, f.read(cls._header_size)
        )
        f.seek(meta_size + model_size, 1)

        names: list[str] = []
        for _ in range(artifacts_count):
            name_size, content_size = struct.unpack(_Artifact._header_format, f.read(_Artifact._header_size))
            names.append(f.read(name_size).decode())
            f.seek(content_size, 1)

        return tuple(names)


class Protocol(BaseProtocol):
    """Version 1 of the Flama serialization protocol — binary-only legacy reader/writer.

    Binary models packaged as a compressed bytes section under a fixed body header; the wire
    format has no kind discriminator and no per-section compression, so directory bundles
    require :class:`flama.serialize.protocols.v2.Protocol`. Model materialisation is deferred
    to :attr:`~flama.serialize.data_structures.ModelArtifact.model`.
    """

    def dump(self, m: ModelArtifact, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> int:
        """Stream-serialize *m* into *f*.

        :param m: Model artifact to serialise.
        :param f: A seekable writable binary stream.
        :param compression: Compression format name applied uniformly to every section.
        :param kwargs: Forwarded to the framework-specific serializer.
        :return: Total number of body bytes written to *f*.
        :raises UnsupportedProtocol: If *m*'s shape is not representable in v1 (directory source).
        """
        return _Body.pack(m, f, compression=compression, **kwargs)

    def load(
        self,
        f: t.BinaryIO,
        /,
        *,
        compression: types.SerializationCompression,
        **kwargs,
    ) -> ModelArtifact:
        """Stream-deserialize a :class:`ModelArtifact` from *f*.

        :param f: Readable binary stream positioned at the body header.
        :param compression: Compression format used when packing.
        :return: Reconstructed :class:`ModelArtifact`. The returned artifact's :attr:`directory`
            field owns a temp directory kept alive for as long as the artifact is referenced.
        """
        artifact = _Body.unpack(f, compression=compression, **kwargs)

        logger.debug("Model '%s' extracted in directory '%s'", artifact, artifact.directory)

        return artifact

    def meta(self, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> Metadata:
        """Read only the :class:`Metadata` section from *f*."""
        return _Body.unpack_meta(f, compression=compression)

    def manifest(self, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> tuple[str, ...]:
        """Read the bundled artifact names from *f*."""
        return _Body.unpack_manifest(f, compression=compression)
