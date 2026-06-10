"""Version 2 of the Flama serialization protocol.

The body header carries only the section frame sizes; every section is self-describing through a
leading discriminator byte (compression + optional kind). This keeps the protocol family-agnostic
and leaves room for future model kinds (safetensors, ONNX, partial bundles) and vendor-defined
section compressions without bumping the version again.

Wire layout::

    body header                24 b
        meta_size              Q
        artifacts_size         Q
        model_size             Q
    meta section
        compression            B   (SectionCompression: inherit | none | named codec)
        payload                ... compressed JSON bytes
    artifacts section
        compression            B   (resolved once for every artifact in this section)
        count                  I
        artifact * count
            name_size          I
            content_size       Q
            name               utf-8 bytes
            content            payload bytes
    model section
        compression            B
        kind                   B   (SerializationModelKind: binary | bundle)
        payload                ... raw bytes (binary) or tar stream (bundle)

Per-section compression resolution: ``"inherit"`` falls back to the file-level compression
(threaded in via :class:`~flama.serialize.serializer.Serializer`'s ``compression`` argument);
:data:`None` is the explicit passthrough; named codecs (``"bz2"``/``"lzma"``/``"zlib"``/``"zstd"``)
override the file-level choice. Unknown bytes raise
:class:`~flama.serialize.exceptions.UnknownCompression` so partial readers never silently
mis-decode payloads.
"""

import json
import logging
import pathlib
import struct
import typing as t

from flama import types
from flama._core.compression import compress, decompress, tar, untar_from
from flama._core.json_encoder import encode_json
from flama.serialize.data_structures import Artifacts, Metadata, ModelArtifact, ModelDirectory
from flama.serialize.exceptions import UnknownCompression, UnknownModelKind, UnsupportedProtocol
from flama.serialize.model_serializers import ModelSerializer
from flama.serialize.protocols._base import BaseProtocol

__all__ = ["Protocol"]

logger = logging.getLogger(__name__)


SectionCompression = types.SerializationCompression | t.Literal["inherit"] | None


class _Compression:
    """Section-aware codec with a resolved algorithm.

    Holds a single algorithm (``None`` means passthrough) and owns the wire-byte mapping. Each
    section in the v2 body builds a sub-instance via :meth:`derive`, which resolves
    ``"inherit"`` against the parent's algorithm so call sites never juggle the file-level
    default by hand.
    """

    _BYTE_TO_NAME: t.ClassVar[dict[int, SectionCompression]] = {
        0x00: "inherit",
        0x01: "bz2",
        0x02: "lzma",
        0x03: "zlib",
        0x04: "zstd",
        0xFF: None,
    }
    _NAME_TO_BYTE: t.ClassVar[dict[SectionCompression, int]] = {v: k for k, v in _BYTE_TO_NAME.items()}

    def __init__(self, algo: types.SerializationCompression | None, /) -> None:
        self._algo = algo

    @property
    def algo(self) -> types.SerializationCompression | None:
        """Resolved codec name (:data:`None` for passthrough)."""
        return self._algo

    def compress(self, data: bytes, /) -> bytes:
        """Encode *data* under the resolved algorithm, treating :data:`None` as passthrough."""
        return data if self._algo is None else compress(data, self._algo)

    def decompress(self, data: bytes, /) -> bytes:
        """Decode *data* under the resolved algorithm, treating :data:`None` as passthrough."""
        return data if self._algo is None else decompress(data, self._algo)

    def byte(self, knob: SectionCompression, /) -> int:
        """Encode a section-compression knob to its wire byte.

        :raises UnknownCompression: When *knob* is not one of the supported literals.
        """
        try:
            return self._NAME_TO_BYTE[knob]
        except KeyError as exc:
            raise UnknownCompression(str(knob)) from exc

    def derive(self, knob: SectionCompression | int, /) -> "_Compression":
        """Build a sub-compression honouring *knob* (literal name or raw wire byte).

        ``"inherit"`` resolves to this compression's algorithm; named codecs override; :data:`None`
        passes through. Integers go through the wire-byte mapping first.

        :raises UnknownCompression: When *knob* is an integer outside the supported byte range.
        """
        if isinstance(knob, int):
            try:
                resolved: SectionCompression = self._BYTE_TO_NAME[knob]
            except KeyError as exc:
                raise UnknownCompression(knob) from exc
        else:
            resolved = knob
        return _Compression(self._algo if resolved == "inherit" else resolved)


class _Kind:
    """Wire-level model-kind discriminator with a resolved name.

    Mirrors :class:`_Compression`'s ``algo`` / ``byte`` pattern: instances carry a resolved kind
    name and expose the wire byte; class-method constructors build them from a :class:`Metadata`
    (dump side) or a wire byte (load side). Vendor-coded or reserved bytes surface as
    :class:`~flama.serialize.exceptions.UnknownModelKind` rather than silently mis-routing the
    payload.
    """

    _BYTE_TO_NAME: t.ClassVar[dict[int, types.SerializationModelKind]] = {0x00: "binary", 0x01: "bundle"}
    _NAME_TO_BYTE: t.ClassVar[dict[types.SerializationModelKind, int]] = {v: k for k, v in _BYTE_TO_NAME.items()}
    _BUNDLE_LIBS: t.ClassVar[frozenset[types.ModelLib]] = frozenset({"transformers"})

    def __init__(self, name: types.SerializationModelKind, /) -> None:
        self._name = name

    @property
    def name(self) -> types.SerializationModelKind:
        """Resolved kind name."""
        return self._name

    @property
    def byte(self) -> int:
        """Wire byte for the resolved kind."""
        return self._NAME_TO_BYTE[self._name]

    @classmethod
    def from_meta(cls, meta: Metadata, /) -> "_Kind":
        """Pick the on-wire kind for *meta*'s model section.

        LLM artifacts and transformers-flavoured ML artifacts pack as ``"bundle"`` (on-disk tar);
        every other ML framework packs as ``"binary"``.
        """
        if meta.framework.family == "llm" or meta.framework.lib in cls._BUNDLE_LIBS:
            return cls("bundle")
        return cls("binary")

    @classmethod
    def from_byte(cls, byte: int, /) -> "_Kind":
        """Decode a wire byte to a :class:`_Kind`.

        :raises UnknownModelKind: When *byte* is outside the supported range.
        """
        try:
            return cls(cls._BYTE_TO_NAME[byte])
        except KeyError as exc:
            raise UnknownModelKind(byte) from exc


class _Artifact:
    """A single bundled sidecar packed within an artifacts section.

    The compression algorithm is resolved once for the entire artifacts section and shared by
    every entry; that's why an :class:`_Artifact` instance is bound to a :class:`_Compression`
    rather than re-deriving per entry.
    """

    _header_format: t.ClassVar[str] = "!I Q"
    _header_size: t.ClassVar[int] = struct.calcsize(_header_format)

    def __init__(self, compression: _Compression, /) -> None:
        self._compression = compression

    def pack(self, name: str, path: pathlib.Path, /) -> bytes:
        """Pack a single named artifact under the section's resolved compression.

        :param name: Name to record on the wire.
        :param path: Source file to read and compress.
        :return: Wire frame: ``(name_size, content_size, name, compressed content)``.
        """
        with path.open("rb") as f:
            body = self._compression.compress(f.read())

        return b"".join((struct.pack(self._header_format, len(name), len(body)), name.encode(), body))

    def unpack(self, b: bytes, /, *, directory: pathlib.Path) -> tuple[pathlib.Path, int]:
        """Unpack a single artifact entry from *b* into *directory*.

        :return: Tuple of the materialised path and the number of bytes consumed from *b*.
        """
        name_size, content_size = struct.unpack(self._header_format, b[: self._header_size])
        offset = self._header_size

        name = b[offset : offset + name_size].decode()
        offset += name_size

        content = b[offset : offset + content_size]

        path = directory / name
        with path.open("wb") as f:
            f.write(self._compression.decompress(content))

        return path, self._header_size + name_size + content_size


class _Body:
    """Section orchestrator for the v2 wire body.

    Holds the file-level compression as a :class:`_Compression` instance and delegates wire-byte
    bookkeeping to :class:`_Compression` (sections) and :class:`_Kind` (model discriminator).
    Each section reads/writes a single header byte (or two for the model section) and threads its
    derived compression through the payload codec.
    """

    _header_format: t.ClassVar[str] = "!Q Q Q"
    _header_size: t.ClassVar[int] = struct.calcsize(_header_format)
    _meta_header_format: t.ClassVar[str] = "!B"
    _meta_header_size: t.ClassVar[int] = struct.calcsize(_meta_header_format)
    _artifacts_header_format: t.ClassVar[str] = "!B I"
    _artifacts_header_size: t.ClassVar[int] = struct.calcsize(_artifacts_header_format)
    _model_header_format: t.ClassVar[str] = "!B B"
    _model_header_size: t.ClassVar[int] = struct.calcsize(_model_header_format)

    def __init__(self, compression: types.SerializationCompression, /) -> None:
        self._compression = _Compression(compression)

    def _pack_meta(self, meta: Metadata, /, *, compression: SectionCompression) -> bytes:
        """Pack the meta section: compression byte + (optionally compressed) JSON payload."""
        sub = self._compression.derive(compression)
        payload = sub.compress(encode_json(meta.to_dict(), compact=True))
        return struct.pack(self._meta_header_format, self._compression.byte(compression)) + payload

    def _pack_artifacts(self, artifacts: Artifacts | None, /, *, compression: SectionCompression) -> bytes:
        """Pack the artifacts section: compression byte + count + each artifact entry."""
        sub = self._compression.derive(compression)
        builder = _Artifact(sub)
        entries = b"".join(builder.pack(name, pathlib.Path(str(p))) for name, p in (artifacts or {}).items())
        return (
            struct.pack(self._artifacts_header_format, self._compression.byte(compression), len(artifacts or {}))
            + entries
        )

    def _pack_model(self, m: ModelArtifact, f: t.BinaryIO, /, *, compression: SectionCompression, **kwargs) -> None:
        """Pack the model section: compression byte + kind byte + payload.

        ``bundle`` + directory streams tar directly into *f*; every other shape resolves to a byte
        payload (pre-serialised :data:`bytes` or a live model passed through the framework
        serializer) and is compressed in one place. A directory source paired with a binary kind
        has no wire encoding in v2 and raises :class:`UnsupportedProtocol`.
        """
        kind = _Kind.from_meta(m.meta)
        f.write(struct.pack(self._model_header_format, self._compression.byte(compression), kind.byte))
        sub = self._compression.derive(compression)

        if kind.name == "bundle" and isinstance(m.source, pathlib.Path):
            tar(str(m.source), f, format=sub.algo)
            return

        if isinstance(m.source, pathlib.Path):
            raise UnsupportedProtocol(
                protocol=2,
                reason=f"binary-kind {m.meta.framework.lib!r} model from a directory source",
            )

        payload = (
            m.source
            if isinstance(m.source, bytes)
            else ModelSerializer.from_lib(m.meta.framework.lib).dump(m.model, **kwargs)
        )
        f.write(sub.compress(payload))

    def pack(self, m: ModelArtifact, f: t.BinaryIO, /, **kwargs) -> int:
        """Stream-serialize *m* into *f*.

        Body header sizes are unknown until each section is fully written; a placeholder header is
        emitted first and patched once the sizes are known.

        :param m: Model artifact to serialise.
        :param f: A seekable writable binary stream.
        :param kwargs: Forwarded to the framework-specific serializer. ``meta_compression``,
            ``artifact_compression`` and ``model_compression`` (each a :class:`SectionCompression`
            literal or wire byte) override the per-section algorithm; all default to ``"inherit"``.
        :return: Total number of body bytes written to *f*.
        :raises UnsupportedProtocol: If *m*'s kind / source pair has no v2 wire encoding (e.g. a
            binary-kind ML model with a directory source).
        """
        meta_compression: SectionCompression = kwargs.pop("meta_compression", "inherit")
        artifact_compression: SectionCompression = kwargs.pop("artifact_compression", "inherit")
        model_compression: SectionCompression = kwargs.pop("model_compression", "inherit")

        body_start = f.tell()
        f.write(b"\x00" * self._header_size)

        meta_bytes = self._pack_meta(m.meta, compression=meta_compression)
        f.write(meta_bytes)

        artifacts_bytes = self._pack_artifacts(m.artifacts, compression=artifact_compression)
        f.write(artifacts_bytes)

        model_start = f.tell()
        self._pack_model(m, f, compression=model_compression, **kwargs)
        model_size = f.tell() - model_start

        body_end = f.tell()
        f.seek(body_start)
        f.write(struct.pack(self._header_format, len(meta_bytes), len(artifacts_bytes), model_size))
        f.seek(body_end)

        return body_end - body_start

    def _unpack_meta(self, b: bytes, /) -> Metadata:
        """Unpack a meta section frame (compression byte + payload)."""
        (byte,) = struct.unpack(self._meta_header_format, b[: self._meta_header_size])
        sub = self._compression.derive(byte)
        return Metadata.from_dict(json.loads(sub.decompress(b[self._meta_header_size :]).decode()))

    def _unpack_artifacts(self, b: bytes, /, *, directory: pathlib.Path) -> Artifacts:
        """Unpack an artifacts section frame (compression byte + count + entries)."""
        byte, count = struct.unpack(self._artifacts_header_format, b[: self._artifacts_header_size])
        sub = self._compression.derive(byte)
        builder = _Artifact(sub)

        directory.mkdir(exist_ok=True)
        artifacts: Artifacts = {}
        offset = self._artifacts_header_size
        for _ in range(count):
            artifact, consumed = builder.unpack(b[offset:], directory=directory)
            artifacts[artifact.name] = artifact
            offset += consumed
        return artifacts

    def _unpack_model(self, f: t.BinaryIO, /, *, size: int, directory: pathlib.Path) -> bytes | pathlib.Path:
        """Unpack a model section frame and return its wire-level source (bytes or directory path).

        Materialisation into a live framework object is deferred to
        :attr:`flama.serialize.data_structures.ModelArtifact.model`, keeping the protocol
        family-agnostic.

        The stream is always advanced to ``start + size`` on return so subsequent reads land on the
        next section even when streaming decompression stops short.
        """
        start = f.tell()
        try:
            byte, kind_byte = struct.unpack(self._model_header_format, f.read(self._model_header_size))
            kind = _Kind.from_byte(kind_byte)
            sub = self._compression.derive(byte)
            payload_size = size - self._model_header_size

            if kind.name == "bundle":
                model_dir = directory / "model"
                model_dir.mkdir(exist_ok=True)
                untar_from(f, str(model_dir), format=sub.algo, length=payload_size)
                return model_dir

            return sub.decompress(f.read(payload_size))
        finally:
            f.seek(start + size)

    def unpack(self, f: t.BinaryIO, /, **kwargs) -> ModelArtifact:
        """Deserialize a :class:`ModelArtifact` from *f* positioned at the body header.

        Owns the temporary directory used during extraction: a fresh :class:`ModelDirectory` is
        created and bound on the returned artifact so its lifetime is tied to the artifact reference.

        :return: Reconstructed :class:`ModelArtifact` with its :attr:`directory` field bound and its
            :attr:`source` set to the wire-level model payload (bytes or extracted directory path).
        """
        meta_size, artifacts_size, model_size = struct.unpack(self._header_format, f.read(self._header_size))

        directory = ModelDirectory()
        meta = self._unpack_meta(f.read(meta_size))
        artifacts = self._unpack_artifacts(f.read(artifacts_size), directory=directory.directory / "artifacts")
        source = self._unpack_model(f, size=model_size, directory=directory.directory)

        return ModelArtifact(meta=meta, source=source, artifacts=artifacts, directory=directory)

    def unpack_meta(self, f: t.BinaryIO, /) -> Metadata:
        """Read only the :class:`Metadata` section from *f* positioned at the body header.

        Reads the body header to determine the metadata frame size, decodes that frame, and stops
        without touching the artifact or model sections. The stream is left positioned past the
        metadata frame.
        """
        meta_size, _artifacts_size, _model_size = struct.unpack(self._header_format, f.read(self._header_size))
        return self._unpack_meta(f.read(meta_size))

    def unpack_manifest(self, f: t.BinaryIO, /) -> tuple[str, ...]:
        """Read the bundled artifact names from *f*.

        Walks the artifacts section header (compression byte + count) and the per-entry headers to
        collect names, seeking past each content payload — never decompressing or decoding any
        metadata, model body, or artifact payload. Cheapest possible introspection.
        """
        meta_size, _artifacts_size, _model_size = struct.unpack(self._header_format, f.read(self._header_size))
        f.seek(meta_size, 1)

        _section_byte, count = struct.unpack(self._artifacts_header_format, f.read(self._artifacts_header_size))

        names: list[str] = []
        for _ in range(count):
            name_size, content_size = struct.unpack(_Artifact._header_format, f.read(_Artifact._header_size))
            names.append(f.read(name_size).decode())
            f.seek(content_size, 1)

        return tuple(names)


class Protocol(BaseProtocol):
    """Version 2 of the Flama serialization protocol.

    Same on-disk envelope as v1 (file-level ``protocol_version`` / ``compression`` / ``body_size``
    header), but the body is now self-describing: each section (meta, artifacts, model) declares
    its own compression byte, the artifacts section carries its own count, and the model section
    carries a kind discriminator. The protocol stays family-agnostic; model materialisation is
    deferred to :attr:`~flama.serialize.data_structures.ModelArtifact.model`.
    """

    def dump(self, m: ModelArtifact, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> int:
        """Stream-serialize *m* into *f*.

        :param m: Model artifact to serialise.
        :param f: A seekable writable binary stream.
        :param compression: File-level compression name; sections may override or opt out via the
            ``meta_compression`` / ``artifact_compression`` / ``model_compression`` kwargs.
        :param kwargs: Forwarded to the framework-specific serializer (and the per-section
            compression overrides above).
        :return: Total number of body bytes written to *f*.
        :raises UnsupportedProtocol: If *m*'s kind / source pair has no v2 wire encoding.
        """
        return _Body(compression).pack(m, f, **kwargs)

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
        :param compression: File-level compression name (inherited by sections whose compression
            byte resolves to ``"inherit"``).
        :return: Reconstructed :class:`ModelArtifact`. The returned artifact's :attr:`directory`
            field owns a temp directory kept alive for as long as the artifact is referenced.
        """
        artifact = _Body(compression).unpack(f, **kwargs)

        logger.debug("Model '%s' extracted in directory '%s'", artifact, artifact.directory)

        return artifact

    def meta(self, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> Metadata:
        """Read only the :class:`Metadata` section from *f*."""
        return _Body(compression).unpack_meta(f)

    def manifest(self, f: t.BinaryIO, /, *, compression: types.SerializationCompression, **kwargs) -> tuple[str, ...]:
        """Read the bundled artifact names from *f*."""
        return _Body(compression).unpack_manifest(f)
