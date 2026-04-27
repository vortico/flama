import dataclasses
import datetime
import enum
import inspect
import logging
import os
import pathlib
import shutil
import tempfile
import typing as t
import uuid
import weakref

from flama import types
from flama.serialize.model_serializers import ModelSerializer

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

__all__ = ["CompressionFormat", "ModelArtifact", "ModelDirectory"]

logger = logging.getLogger(__name__)


class CompressionFormat(enum.IntEnum):
    """Stable integer ids for the compression algorithm stored in the binary serialization header."""

    bz2 = 1
    lzma = 2
    zlib = 3
    zstd = 4


class ModelDirectory:
    """Temporary directory holding files extracted from a serialized model.

    The directory is created on construction and cleaned up via a :class:`weakref.finalize`
    when the instance is garbage-collected, unless *delete* is ``False``.

    :param delete: Whether to remove the directory automatically on finalisation.
    """

    def __init__(self, delete: bool = True) -> None:
        self.directory = pathlib.Path(tempfile.mkdtemp())

        self._finalizer = weakref.finalize(self, self._cleanup) if delete else None

    def __str__(self) -> str:
        return str(self.directory)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(directory={self.directory!r})"

    def _cleanup(self) -> None:
        logger.debug("Model directory '%s' clean", self.directory)
        shutil.rmtree(self.directory)

    def exists(self) -> bool:
        """Check if the model directory exists.

        :return: True if the directory exists.
        """
        return self.directory.exists()

    def cleanup(self) -> None:
        """Clean the model directory by removing it."""
        if (self._finalizer and self._finalizer.detach()) or self.exists():
            self._cleanup()


@dataclasses.dataclass
class FrameworkInfo:
    """Dataclass for storing model framework information."""

    lib: types.Lib
    version: str
    config: dict[str, t.Any] | None = None

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        lib: types.Lib | None = None,
        config: dict[str, t.Any] | None = None,
    ) -> "FrameworkInfo":
        serializer = ModelSerializer.from_lib(lib) if lib else ModelSerializer.from_model(model)
        return cls(lib=serializer.lib, version=serializer.version(), config=config)

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "FrameworkInfo":
        return cls(lib=data["lib"], version=data["version"], config=data.get("config"))

    def to_dict(self) -> dict[str, t.Any]:
        return {"lib": self.lib, "version": self.version, "config": self.config}


@dataclasses.dataclass
class ModelInfo:
    """Dataclass for storing model info."""

    obj: str
    info: "JSONSchema | None" = None
    params: dict[str, t.Any] | None = None
    metrics: dict[str, t.Any] | None = None

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        params: dict[str, t.Any] | None,
        metrics: dict[str, t.Any] | None,
        *,
        lib: types.Lib | None = None,
    ) -> "ModelInfo":
        serializer = ModelSerializer.from_lib(lib) if lib else ModelSerializer.from_model(model)
        return cls(
            obj=model.__name__ if inspect.isclass(model) else model.__class__.__name__,
            info=serializer.info(model),
            params=params,
            metrics=metrics,
        )

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "ModelInfo":
        return cls(obj=data["obj"], info=data["info"], params=data.get("params"), metrics=data.get("metrics"))

    def to_dict(self) -> dict[str, t.Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class Metadata:
    """Dataclass for storing model metadata."""

    id: str | uuid.UUID
    timestamp: datetime.datetime
    framework: FrameworkInfo
    model: ModelInfo
    extra: dict[str, t.Any] | None = None

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        model_id: str | uuid.UUID | None,
        timestamp: datetime.datetime | None,
        params: dict[str, t.Any] | None,
        metrics: dict[str, t.Any] | None,
        extra: dict[str, t.Any] | None,
        config: dict[str, t.Any] | None = None,
        lib: types.Lib | None = None,
    ) -> "Metadata":
        return cls(
            id=model_id or uuid.uuid4(),
            timestamp=timestamp or datetime.datetime.now(),
            framework=FrameworkInfo.from_model(model, lib=lib, config=config),
            model=ModelInfo.from_model(model, params, metrics, lib=lib),
            extra=extra,
        )

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "Metadata":
        try:
            id_ = uuid.UUID(data["id"])
        except ValueError:  # pragma: no cover
            id_ = data["id"]

        timestamp = (
            datetime.datetime.fromisoformat(data["timestamp"])
            if isinstance(data["timestamp"], str)
            else data["timestamp"]
        )

        return cls(
            id=id_,
            timestamp=timestamp,
            framework=FrameworkInfo.from_dict(data["framework"]),
            model=ModelInfo.from_dict(data["model"]),
            extra=data.get("extra"),
        )

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "framework": self.framework.to_dict(),
            "model": self.model.to_dict(),
            "extra": self.extra,
        }


Artifacts = dict[str, str | os.PathLike | pathlib.Path]


@dataclasses.dataclass(frozen=True)
class ModelArtifact:
    """ML Model wrapper to provide mechanisms for serialization and deserialization using Flama format.

    The optional :attr:`directory` field carries the lifetime of a :class:`ModelDirectory` extracted
    during deserialization. It is excluded from equality, hashing and ``repr`` because it is a runtime
    resource, not part of the model identity.
    """

    meta: Metadata
    model: t.Any
    artifacts: Artifacts | None = None
    directory: ModelDirectory | None = dataclasses.field(default=None, repr=False, compare=False, hash=False)

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        model_id: str | uuid.UUID | None = None,
        timestamp: datetime.datetime | None = None,
        params: dict[str, t.Any] | None = None,
        metrics: dict[str, t.Any] | None = None,
        extra: dict[str, t.Any] | None = None,
        config: dict[str, t.Any] | None = None,
        artifacts: Artifacts | None = None,
        lib: types.Lib | None = None,
    ) -> "ModelArtifact":
        return cls(
            meta=Metadata.from_model(
                model,
                model_id=model_id,
                timestamp=timestamp,
                params=params,
                metrics=metrics,
                extra=extra,
                config=config,
                lib=lib,
            ),
            model=model,
            artifacts=artifacts,
        )
