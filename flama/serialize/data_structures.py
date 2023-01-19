import codecs
import dataclasses
import datetime
import importlib
import inspect
import json
import typing as t
import uuid

from flama.serialize.base import Serializer
from flama.serialize.types import Framework


class FrameworkSerializers:
    @classmethod
    def serializer(cls, framework: t.Union[str, Framework]) -> Serializer:
        try:
            module, class_name = {
                Framework.torch: ("pytorch", "PyTorchSerializer"),
                Framework.sklearn: ("sklearn", "SKLearnSerializer"),
                Framework.keras: ("tensorflow", "TensorFlowSerializer"),
                Framework.tensorflow: ("tensorflow", "TensorFlowSerializer"),
            }[Framework(framework)]
        except KeyError:  # pragma: no cover
            raise ValueError("Wrong framework")

        serializer_class: t.Type[Serializer] = getattr(
            importlib.import_module(f"flama.serialize.serializers.{module}"), class_name
        )
        return serializer_class()

    @classmethod
    def from_model(cls, model: t.Any) -> Serializer:
        inspect_objs = [model]

        try:
            inspect_objs += model.__class__.__mro__
        except AttributeError:
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
    def from_dict(cls, data: t.Dict[str, t.Any]) -> "FrameworkInfo":
        return cls(lib=Framework[data["lib"]], version=data["version"])

    def to_dict(self) -> t.Dict[str, t.Any]:
        return {"lib": self.lib.value, "version": self.version}


@dataclasses.dataclass
class ModelInfo:
    """Dataclass for storing model info."""

    obj: str
    info: t.Dict[str, t.Any]
    params: t.Optional[t.Dict[str, t.Any]] = None
    metrics: t.Optional[t.Dict[str, t.Any]] = None

    @classmethod
    def from_model(
        cls, model: t.Any, params: t.Optional[t.Dict[str, t.Any]], metrics: t.Optional[t.Dict[str, t.Any]]
    ) -> "ModelInfo":
        return cls(
            obj=model.__name__ if inspect.isclass(model) else model.__class__.__name__,
            info=FrameworkSerializers.from_model(model).info(model),
            params=params,
            metrics=metrics,
        )

    @classmethod
    def from_dict(cls, data: t.Dict[str, t.Any]):
        return cls(obj=data["obj"], info=data["info"], params=data.get("params"), metrics=data.get("metrics"))

    def to_dict(self) -> t.Dict[str, t.Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class Metadata:
    """Dataclass for storing model metadata."""

    id: t.Union[str, uuid.UUID]
    timestamp: datetime.datetime
    framework: FrameworkInfo
    model: ModelInfo
    extra: t.Optional[t.Dict[str, t.Any]] = None

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        model_id: t.Optional[t.Union[str, uuid.UUID]],
        timestamp: t.Optional[datetime.datetime],
        params: t.Optional[t.Dict[str, t.Any]],
        metrics: t.Optional[t.Dict[str, t.Any]],
        extra: t.Optional[t.Dict[str, t.Any]],
    ) -> "Metadata":
        return cls(
            id=model_id or uuid.uuid4(),
            timestamp=timestamp or datetime.datetime.now(),
            framework=FrameworkInfo.from_model(model),
            model=ModelInfo.from_model(model, params, metrics),
            extra=extra,
        )

    @classmethod
    def from_dict(cls, data: t.Dict[str, t.Any]) -> "Metadata":
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

    def to_dict(self) -> t.Dict[str, t.Any]:
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "framework": self.framework.to_dict(),
            "model": self.model.to_dict(),
            "extra": self.extra,
        }


@dataclasses.dataclass(frozen=True)
class ModelArtifact:
    """ML Model wrapper to provide mechanisms for serialization and deserialization using Flama format."""

    model: t.Any
    meta: Metadata

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        model_id: t.Optional[t.Union[str, uuid.UUID]] = None,
        timestamp: t.Optional[datetime.datetime] = None,
        params: t.Optional[t.Dict[str, t.Any]] = None,
        metrics: t.Optional[t.Dict[str, t.Any]] = None,
        extra: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> "ModelArtifact":
        return cls(
            model=model,
            meta=Metadata.from_model(
                model, model_id=model_id, timestamp=timestamp, params=params, metrics=metrics, extra=extra
            ),
        )

    @classmethod
    def from_dict(cls, data: t.Dict[str, t.Any], **kwargs) -> "ModelArtifact":
        try:
            metadata = Metadata.from_dict(data["meta"])
            model = FrameworkSerializers.serializer(metadata.framework.lib).load(data["model"].encode(), **kwargs)
        except KeyError:  # pragma: no cover
            raise ValueError("Wrong data")

        return cls(model=model, meta=metadata)

    @classmethod
    def from_json(cls, data: str, **kwargs) -> "ModelArtifact":
        return cls.from_dict(json.loads(data), **kwargs)

    @classmethod
    def from_bytes(cls, data: bytes, **kwargs) -> "ModelArtifact":
        return cls.from_json(codecs.decode(data, "zlib"), **kwargs)  # type: ignore[arg-type]

    def to_dict(self, **kwargs) -> t.Dict[str, t.Any]:
        return {
            "model": FrameworkSerializers.serializer(self.meta.framework.lib).dump(self.model, **kwargs).decode(),
            "meta": self.meta.to_dict(),
        }

    def to_json(self, **kwargs) -> str:
        return json.dumps(self.to_dict(**kwargs))

    def to_bytes(self, **kwargs) -> bytes:
        return codecs.encode(self.to_json(**kwargs).encode(), "zlib")
