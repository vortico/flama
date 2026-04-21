import dataclasses
import datetime
import inspect
import logging
import os
import pathlib
import typing as t
import uuid

from flama import types
from flama.serialize.model_serializers import ModelSerializer

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

__all__ = ["ModelArtifact"]

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class FrameworkInfo:
    """Dataclass for storing model framework information."""

    lib: types.MLLib
    version: str
    config: dict[str, t.Any] | None = None

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        lib: types.MLLib | None = None,
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
        lib: types.MLLib | None = None,
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
        lib: types.MLLib | None = None,
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
    """ML Model wrapper to provide mechanisms for serialization and deserialization using Flama format."""

    meta: Metadata
    model: t.Any
    artifacts: Artifacts | None = None

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
        lib: types.MLLib | None = None,
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
