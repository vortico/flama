import io
import json
import logging
import pathlib
import shutil
import struct
import tarfile
import tempfile
import typing as t
import weakref

from flama import types
from flama._core.json_encoder import encode_json
from flama.serialize.compression import Compression
from flama.serialize.data_structures import Artifacts, Metadata, ModelArtifact
from flama.serialize.model_serializers import ModelSerializer
from flama.serialize.protocols.base import BaseProtocol

__all__ = ["Protocol"]

logger = logging.getLogger(__name__)


class _ModelDirectory:  # pragma: no cover
    def __init__(self, delete: bool = True):
        """Generate a model directory from a model file."""
        self.directory = pathlib.Path(tempfile.mkdtemp())

        self._finalizer = weakref.finalize(self, self._cleanup) if delete else None

    def _cleanup(self):
        logger.debug("Model directory '%s' clean", self.directory)
        shutil.rmtree(self.directory)

    def exists(self) -> bool:
        """Check if the model directory exists.

        :return: True if the directory exists.
        """
        return self.directory.exists()

    def cleanup(self):
        """Clean the model directory by removing it."""
        if (self._finalizer and self._finalizer.detach()) or self.exists():
            self._cleanup()


class _Artifact:
    _header_format: t.ClassVar[str] = "!I Q"
    _header_size: t.ClassVar[int] = struct.calcsize(_header_format)

    @classmethod
    def pack(cls, name: str, path: pathlib.Path, /, *, compression: Compression, **kwargs) -> bytes:
        with path.open("rb") as f:
            body = compression.compress(f.read())

        return b"".join(
            (
                struct.pack(cls._header_format, len(name), len(body)),
                name.encode(),
                body,
            )
        )

    @classmethod
    def unpack(
        cls, b: bytes, /, *, compression: Compression, directory: pathlib.Path, **kwargs
    ) -> tuple[pathlib.Path, int]:
        name_size, content_size = struct.unpack(cls._header_format, b[: cls._header_size])
        offset = cls._header_size

        name = (b[offset : offset + name_size]).decode()
        offset += name_size

        content = b[offset : offset + content_size]

        path = directory / name
        with path.open("wb") as f:
            f.write(compression.decompress(content))

        return path, cls._header_size + name_size + content_size


class _Body:
    _header_format: t.ClassVar[str] = "!Q Q I Q"
    _header_size: t.ClassVar[int] = struct.calcsize(_header_format)

    @staticmethod
    def _pack_meta(meta: Metadata, *, compression: Compression) -> bytes:
        return compression.compress(encode_json(meta.to_dict(), compact=True))

    @staticmethod
    def _pack_model(model: t.Any, *, lib: types.MLLib, compression: Compression, **kwargs) -> bytes:
        return compression.compress(ModelSerializer.from_lib(lib).dump(model, **kwargs))

    @staticmethod
    def _pack_artifacts(artifacts: Artifacts | None, *, compression: Compression) -> tuple[int, bytes]:
        return len(artifacts) if artifacts else 0, b"".join(
            _Artifact.pack(name, pathlib.Path(str(path)), compression=compression)
            for name, path in (artifacts or {}).items()
        )

    @classmethod
    def pack(cls, m: ModelArtifact, /, *, compression: Compression, **kwargs) -> bytes:
        meta = cls._pack_meta(m.meta, compression=compression)
        model = cls._pack_model(m.model, lib=m.meta.framework.lib, compression=compression, **kwargs)
        artifacts_count, artifacts = cls._pack_artifacts(m.artifacts, compression=compression)

        header = struct.pack(cls._header_format, len(meta), len(model), artifacts_count, len(artifacts))
        return b"".join((header, meta, model, artifacts))

    @staticmethod
    def _unpack_meta(b: bytes, *, compression: Compression) -> Metadata:
        return Metadata.from_dict(json.loads(compression.decompress(b).decode()))

    @staticmethod
    def _unpack_model(b: bytes, *, meta: Metadata, compression: Compression, directory: pathlib.Path) -> t.Any:
        model_bytes = compression.decompress(b)

        load_kwargs: dict[str, t.Any] = {}

        if model_bytes and tarfile.is_tarfile(io.BytesIO(model_bytes)):
            model_dir = directory / "model"
            model_dir.mkdir(exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(model_bytes)) as tf:
                tf.extractall(model_dir, filter="data")
            load_kwargs["model_dir"] = model_dir

        if meta.framework.config:
            load_kwargs.update(meta.framework.config)

        return ModelSerializer.from_lib(meta.framework.lib).load(model_bytes, **load_kwargs)

    @staticmethod
    def _unpack_artifacts(b: bytes, *, count: int, compression: Compression, directory: pathlib.Path) -> Artifacts:
        directory.mkdir(exist_ok=True)
        artifacts: Artifacts = {}
        offset = 0
        for _ in range(count):
            artifact, size = _Artifact.unpack(b[offset:], compression=compression, directory=directory)
            artifacts[artifact.name] = artifact
            offset += size
        return artifacts

    @classmethod
    def unpack(cls, b: bytes, /, *, compression: Compression, directory: pathlib.Path, **kwargs) -> ModelArtifact:
        meta_size, model_size, artifacts_count, artifacts_size = struct.unpack(
            cls._header_format, b[: cls._header_size]
        )

        offset = cls._header_size
        meta = cls._unpack_meta(b[offset : offset + meta_size], compression=compression)

        offset += meta_size
        model = cls._unpack_model(
            b[offset : offset + model_size], meta=meta, compression=compression, directory=directory
        )

        offset += model_size
        artifacts = cls._unpack_artifacts(
            b[offset : offset + artifacts_size],
            count=artifacts_count,
            compression=compression,
            directory=directory / "artifacts",
        )

        return ModelArtifact(meta=meta, model=model, artifacts=artifacts)


class Protocol(BaseProtocol):
    def dump(self, m: ModelArtifact, /, *, compression: Compression, **kwargs) -> bytes:
        return _Body.pack(m, compression=compression)

    def load(self, b: bytes, /, *, compression: Compression, **kwargs) -> ModelArtifact:
        directory = _ModelDirectory()
        artifact = _Body.unpack(b, compression=compression, directory=directory.directory)

        # Keep the temp directory alive as long as the artifact (frozen dataclass)
        object.__setattr__(artifact, "_directory", directory)

        logger.debug("Model '%s' extracted in directory '%s'", artifact, directory)

        return artifact
