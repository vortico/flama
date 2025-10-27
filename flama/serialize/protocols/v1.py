import json
import logging
import pathlib
import shutil
import struct
import tempfile
import typing as t
import weakref

from flama.serialize.compression import Compression
from flama.serialize.data_structures import Metadata, ModelArtifact
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

    @classmethod
    def pack(cls, m: ModelArtifact, /, *, compression: Compression, **kwargs) -> bytes:
        meta = compression.compress(json.dumps(m.meta.to_dict()).encode())
        model = compression.compress(ModelSerializer.from_lib(m.meta.framework.lib).dump(m.model))
        artifacts = b"".join(
            _Artifact.pack(name, pathlib.Path(str(path)), compression=compression)
            for name, path in (m.artifacts or {}).items()
        )
        header = struct.pack(
            cls._header_format, len(meta), len(model), len(m.artifacts) if m.artifacts else 0, len(artifacts)
        )

        return b"".join((header, meta, model, artifacts))

    @classmethod
    def unpack(cls, b: bytes, /, *, compression: Compression, directory: pathlib.Path, **kwargs) -> ModelArtifact:
        meta_size, model_size, artifacts_number, artifacts_size = struct.unpack(
            cls._header_format, b[: cls._header_size]
        )
        offset = cls._header_size

        meta = Metadata.from_dict(json.loads(compression.decompress(b[offset : offset + meta_size]).decode()))
        offset += meta_size

        model = ModelSerializer.from_lib(meta.framework.lib).load(
            compression.decompress(b[offset : offset + model_size])
        )
        offset += model_size

        artifacts = {}
        artifacts_directory = directory / "artifacts"
        artifacts_directory.mkdir(exist_ok=True)
        for _ in range(artifacts_number):
            artifact, size = _Artifact.unpack(b[offset:], compression=compression, directory=artifacts_directory)
            artifacts[artifact.name] = artifact
            offset += size

        return ModelArtifact(meta=meta, model=model, artifacts=artifacts)


class Protocol(BaseProtocol):
    def dump(self, m: ModelArtifact, /, *, compression: Compression, **kwargs) -> bytes:
        return _Body.pack(m, compression=compression)

    def load(self, b: bytes, /, *, compression: Compression, **kwargs) -> ModelArtifact:
        directory = _ModelDirectory()
        artifact = _Body.unpack(b, compression=compression, directory=directory.directory)

        logger.debug("Model '%s' extracted in directory '%s'", artifact, directory)

        return artifact
