import codecs
import dataclasses
import datetime
import enum
import importlib
import inspect
import json
import logging
import os
import shutil
import tarfile
import tempfile
import typing as t
import uuid
import warnings
import weakref
from pathlib import Path

from flama import compat, exceptions
from flama.serialize.base import Serializer
from flama.serialize.types import Framework

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

__all__ = ["ModelArtifact", "Compression"]

logger = logging.getLogger(__name__)


class Compression(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
    fast = enum.auto()
    standard = enum.auto()
    high = enum.auto()

    @property
    def compression_format(self) -> str:
        return {
            Compression.fast: "gz",
            Compression.standard: "bz2",
            Compression.high: "xz",
        }[self]


class FrameworkSerializers:
    @classmethod
    def serializer(cls, framework: t.Union[str, Framework]) -> Serializer:
        try:
            module, class_name = {
                Framework.torch: ("pytorch", "PyTorchSerializer"),
                Framework.sklearn: ("sklearn", "SKLearnSerializer"),
                Framework.keras: ("tensorflow", "TensorFlowSerializer"),
                Framework.tensorflow: ("tensorflow", "TensorFlowSerializer"),
            }[Framework[framework]]
        except KeyError:  # pragma: no cover
            raise ValueError("Wrong framework")

        serializer_class: type[Serializer] = getattr(
            importlib.import_module(f"flama.serialize.serializers.{module}"), class_name
        )
        return serializer_class()

    @classmethod
    def from_model(cls, model: t.Any) -> Serializer:
        inspect_objs = [model]

        try:
            inspect_objs += model.__class__.__mro__
        except AttributeError:  # pragma: no cover
            ...

        for obj in inspect_objs:
            try:
                return cls.serializer(inspect.getmodule(obj).__name__.split(".", 1)[0])  # type: ignore[union-attr]
            except (ValueError, AttributeError):
                ...
        else:
            raise ValueError("Unknown model framework")


@dataclasses.dataclass
class FrameworkInfo:
    """Dataclass for storing model framework information."""

    lib: Framework
    version: str

    @classmethod
    def from_model(cls, model: t.Any) -> "FrameworkInfo":
        serializer = FrameworkSerializers.from_model(model)
        return cls(lib=serializer.lib, version=serializer.version())

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "FrameworkInfo":
        return cls(lib=Framework[data["lib"]], version=data["version"])

    def to_dict(self) -> dict[str, t.Any]:
        return {"lib": self.lib.value, "version": self.version}


@dataclasses.dataclass
class ModelInfo:
    """Dataclass for storing model info."""

    obj: str
    info: t.Optional["JSONSchema"] = None
    params: t.Optional[dict[str, t.Any]] = None
    metrics: t.Optional[dict[str, t.Any]] = None

    @classmethod
    def from_model(
        cls, model: t.Any, params: t.Optional[dict[str, t.Any]], metrics: t.Optional[dict[str, t.Any]]
    ) -> "ModelInfo":
        return cls(
            obj=model.__name__ if inspect.isclass(model) else model.__class__.__name__,
            info=FrameworkSerializers.from_model(model).info(model),
            params=params,
            metrics=metrics,
        )

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]):
        return cls(obj=data["obj"], info=data["info"], params=data.get("params"), metrics=data.get("metrics"))

    def to_dict(self) -> dict[str, t.Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class Metadata:
    """Dataclass for storing model metadata."""

    id: t.Union[str, uuid.UUID]
    timestamp: datetime.datetime
    framework: FrameworkInfo
    model: ModelInfo
    extra: t.Optional[dict[str, t.Any]] = None

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        model_id: t.Optional[t.Union[str, uuid.UUID]],
        timestamp: t.Optional[datetime.datetime],
        params: t.Optional[dict[str, t.Any]],
        metrics: t.Optional[dict[str, t.Any]],
        extra: t.Optional[dict[str, t.Any]],
    ) -> "Metadata":
        return cls(
            id=model_id or uuid.uuid4(),
            timestamp=timestamp or datetime.datetime.now(),
            framework=FrameworkInfo.from_model(model),
            model=ModelInfo.from_model(model, params, metrics),
            extra=extra,
        )

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "Metadata":
        try:
            id_ = uuid.UUID(data["id"])
        except ValueError:
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


Artifacts = dict[str, t.Union[str, os.PathLike]]


class _ModelDirectory:
    def __init__(
        self,
        model_file: t.Union[str, os.PathLike],
        path: t.Optional[t.Union[str, os.PathLike]] = None,
        delete: bool = True,
    ):
        """Generate a model directory from a model file.

        :param model_file: Model file path.
        :param path: Directory path. Create a temporary directory if None.
        :return: Model directory loaded.
        """
        self.directory = Path(path) if path else Path(tempfile.mkdtemp())

        with tarfile.open(model_file, "r") as tar:
            tar.extractall(self.directory)

        self.model = self.directory / "model"
        self.artifacts: Artifacts = {artifact.name: artifact for artifact in self.directory.glob("artifacts/*")}

        logger.debug("Model '%s' extracted in directory '%s'", model_file, self.directory)

        self._finalizer = weakref.finalize(self, self._cleanup) if delete else None

    def _cleanup(self):
        logger.debug("Model directory '%s' clean", self.directory)
        shutil.rmtree(self.directory)

    def exists(self) -> bool:
        """Check if the model directory exists.

        :return: True if the directory exists.
        """
        return os.path.exists(self.directory)

    def cleanup(self):
        """Clean the model directory by removing it."""
        if (self._finalizer and self._finalizer.detach()) or self.exists():
            self._cleanup()


@dataclasses.dataclass(frozen=True)
class ModelArtifact:
    """ML Model wrapper to provide mechanisms for serialization and deserialization using Flama format."""

    model: t.Any
    meta: Metadata
    artifacts: t.Optional[Artifacts] = None
    _directory: t.Optional[_ModelDirectory] = dataclasses.field(default=None, repr=False, compare=False)

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        model_id: t.Optional[t.Union[str, uuid.UUID]] = None,
        timestamp: t.Optional[datetime.datetime] = None,
        params: t.Optional[dict[str, t.Any]] = None,
        metrics: t.Optional[dict[str, t.Any]] = None,
        extra: t.Optional[dict[str, t.Any]] = None,
        artifacts: t.Optional[Artifacts] = None,
    ) -> "ModelArtifact":
        return cls(
            model=model,
            meta=Metadata.from_model(
                model, model_id=model_id, timestamp=timestamp, params=params, metrics=metrics, extra=extra
            ),
            artifacts=artifacts,
        )

    @classmethod
    def from_dict(cls, data: dict[str, t.Any], **kwargs) -> "ModelArtifact":
        try:
            metadata = Metadata.from_dict(data["meta"])
            artifacts = data.get("artifacts")
            serializer = FrameworkSerializers.serializer(metadata.framework.lib)
            model = serializer.load(data["model"].encode(), **kwargs)
        except KeyError:  # pragma: no cover
            raise ValueError("Wrong data")

        if serializer.version() != metadata.framework.version:  # noqa
            warnings.warn(
                f"Model was built using {metadata.framework.lib.value} '{metadata.framework.version}' but detected "
                f"version '{serializer.version()}' installed. This may cause unexpected behavior.",
                exceptions.FrameworkVersionWarning,
            )

        return cls(model=model, meta=metadata, artifacts=artifacts)

    @classmethod
    def from_json(cls, data: str, **kwargs) -> "ModelArtifact":
        return cls.from_dict(json.loads(data), **kwargs)

    @classmethod
    def from_bytes(cls, data: bytes, **kwargs) -> "ModelArtifact":
        return cls.from_json(codecs.decode(data, "zlib"), **kwargs)  # type: ignore[arg-type]

    def to_dict(self, *, artifacts: bool = True, **kwargs) -> dict[str, t.Any]:
        result: dict[str, t.Any] = {
            "model": FrameworkSerializers.serializer(self.meta.framework.lib).dump(self.model, **kwargs).decode(),
            "meta": self.meta.to_dict(),
        }

        if artifacts:
            result["artifacts"] = self.artifacts

        return result

    def to_json(self, *, artifacts: bool = True, **kwargs) -> str:
        return json.dumps(self.to_dict(artifacts=artifacts, **kwargs))

    def to_bytes(self, *, artifacts: bool = True, **kwargs) -> bytes:
        return codecs.encode(self.to_json(artifacts=artifacts, **kwargs).encode(), "zlib")

    def dump(
        self,
        path: t.Union[str, os.PathLike] = "model.flm",
        compression: t.Union[str, Compression] = Compression.standard,
        **kwargs,
    ) -> None:
        """Serialize model artifact into a file.

        :param path: Model file path.
        :param compression: Compression type.
        :param kwargs: Keyword arguments passed to library dump method.
        """
        logger.info("Dump model '%s'", path)
        with tarfile.open(path, f"w:{Compression[compression].compression_format}") as tar:  # type: ignore
            if self.artifacts:
                for name, path in self.artifacts.items():
                    tar.add(path, f"artifacts/{name}")

            with tempfile.NamedTemporaryFile("wb") as model:
                model.write(self.to_bytes(artifacts=False, **kwargs))
                tar.add(model.name, "model")

    @classmethod
    def load(cls, path: t.Union[str, os.PathLike], **kwargs) -> "ModelArtifact":
        """Deserialize model artifact from a file.

        :param path: Model file path.
        :param kwargs: Keyword arguments passed to library load method.
        :return: Model artifact loaded.
        """
        logger.info("Load model '%s'", path)
        model_directory = _ModelDirectory(path)

        with open(model_directory.model, "rb") as f:
            model_artifact = cls.from_bytes(f.read(), **kwargs)

        return cls(
            model=model_artifact.model,
            meta=model_artifact.meta,
            artifacts=model_directory.artifacts or None,
            _directory=model_directory,
        )
