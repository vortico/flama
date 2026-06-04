import dataclasses
import datetime
import enum
import functools
import inspect
import logging
import os
import pathlib
import shutil
import tempfile
import typing as t
import uuid
import weakref

from flama import exceptions, types
from flama.serialize.model_serializers import ModelSerializer

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

__all__ = [
    "CompressionFormat",
    "LLMModelCapabilities",
    "Metadata",
    "MLModelCapabilities",
    "ModelArtifact",
    "ModelCapabilities",
    "ModelDirectory",
]

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


@dataclasses.dataclass(frozen=True)
class ModelCapabilities:
    """Declarative description of what a packaged model can ingest and produce.

    Subclassed per :data:`~flama.types.ModelFamily` so capability shape can diverge across
    families: :class:`MLModelCapabilities` (traditional ML, no advertised modalities yet) and
    :class:`LLMModelCapabilities` (text + multimodal flags). Subclasses set the
    :attr:`kind` :class:`typing.ClassVar` to their family literal so :meth:`from_dict` can
    deserialise the right concrete type from the manifest.

    Detected at serialize time by each :class:`~flama.serialize.model_serializers.base.BaseModelSerializer`'s
    :meth:`detect_capabilities` and persisted in the ``.flm`` manifest so consumers (backend
    dispatch, input validation, serving-layer advertisement) read a single source of truth
    instead of re-probing the model.
    """

    kind: t.ClassVar[types.ModelFamily]

    @classmethod
    def from_dict(cls, data: dict[str, t.Any], /) -> "ModelCapabilities":
        """Build a :class:`ModelCapabilities` subclass from a flat boolean mapping.

        Reads the ``kind`` discriminator from *data* and instantiates the matching subclass.
        Unknown keys are ignored so older readers can deserialise newer manifests; missing keys
        fall back to dataclass defaults.

        :param data: Flat mapping with at least a ``kind`` discriminator.
        :return: A populated :class:`MLModelCapabilities` or :class:`LLMModelCapabilities`.
        :raises ValueError: If ``kind`` does not match any known subclass.
        :raises KeyError: If the required ``kind`` discriminator is missing.
        """
        kind = data["kind"]
        for sub in cls.__subclasses__():
            if sub.kind == kind:
                fields = {f.name for f in dataclasses.fields(sub)}
                return sub(**{k: bool(v) for k, v in data.items() if k in fields})
        raise ValueError(f"Unknown ModelCapabilities kind: {kind!r}")

    def to_dict(self) -> dict[str, t.Any]:
        """Serialise to a flat mapping suitable for JSON round-trip.

        The ``kind`` discriminator is always emitted so :meth:`from_dict` can pick the right
        concrete subclass on read.
        """
        return {"kind": self.kind, **dataclasses.asdict(self)}


@dataclasses.dataclass(frozen=True)
class MLModelCapabilities(ModelCapabilities):
    """Capabilities for a traditional ML artifact.

    Empty for now. Reserved as a placeholder so future ML-specific capability flags (e.g.
    hardware acceleration hints, batch size limits) have a concrete subclass to land on.
    """

    kind: t.ClassVar[types.ModelFamily] = "ml"


@dataclasses.dataclass(frozen=True)
class LLMModelCapabilities(ModelCapabilities):
    """Capabilities for a large-language-model artifact.

    :param text: Whether the model accepts text input. Defaults to :data:`True` since every LLM
        we handle is text-capable.
    :param image: Whether the model accepts image content parts.
    :param audio: Whether the model accepts audio content parts.
    :param video: Whether the model accepts video content parts.
    :param tools: Whether the model can be advertised with function-tool specs.
    :param reasoning: Whether the model emits a separate ``reasoning_content`` channel.
    """

    kind: t.ClassVar[types.ModelFamily] = "llm"

    text: bool = True
    image: bool = False
    audio: bool = False
    video: bool = False
    tools: bool = False
    reasoning: bool = False

    @property
    def is_multimodal(self) -> bool:
        """Whether any non-text input modality is supported."""
        return self.image or self.audio or self.video

    @property
    def modalities(self) -> tuple[str, ...]:
        """Names of the supported input modalities, in canonical order."""
        return tuple(k for k in ("text", "image", "audio", "video") if getattr(self, k))


@dataclasses.dataclass
class FrameworkInfo:
    """Framework metadata for a packaged artifact.

    Carries two orthogonal discriminators:

    - :attr:`family` (``"ml"`` / ``"llm"``) is the artifact's *intent* at serve time. It is
      chosen by the producer at dump time (e.g. via ``flama get --family llm``) and never
      inferred from :attr:`lib` at load time.
    - :attr:`lib` records the library that actually wrote the bytes on disk. LLM artifacts
      always record ``"transformers"`` because the wire format is a HuggingFace checkpoint
      tarball; the runtime that ultimately serves them (vLLM, MLX, ...) is picked at load
      time by an import probe and is *not* persisted in the manifest.

    :param family: Artifact family - ``"ml"`` for traditional ML models, ``"llm"`` for large
        language models served via vLLM / MLX.
    :param lib: Framework library that produced the on-disk bytes.
    :param version: Version string of :attr:`lib` at dump time.
    :param config: Optional framework-specific configuration forwarded to the backend at load
        time (e.g. ``{"task": "..."}`` for transformers pipelines, ``{"engine_params": {...}}``
        for LLM engine construction).
    """

    family: types.ModelFamily
    lib: types.ModelLib
    version: str
    config: dict[str, t.Any] | None = None

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        family: types.ModelFamily,
        lib: types.ModelLib | None = None,
        config: dict[str, t.Any] | None = None,
    ) -> "FrameworkInfo":
        """Build a :class:`FrameworkInfo` from a live model object or a directory path.

        :param model: Source model object or directory path.
        :param family: Artifact family. Required - never inferred.
        :param lib: Optional override for the producing library. Defaults to detecting from
            *model*.
        :param config: Optional framework-specific configuration to persist.
        """
        serializer = ModelSerializer.from_lib(lib) if lib else ModelSerializer.from_model(model)
        return cls(family=family, lib=serializer.lib, version=serializer.version(), config=config)

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "FrameworkInfo":
        """Decode a :class:`FrameworkInfo` from its dict form.

        Manifests that pre-date the ``family`` discriminator (master-era ``.flm`` files written
        before the ML/LLM split) default to ``"ml"`` so older artifacts keep loading unchanged.
        """
        return cls(family=data.get("family", "ml"), lib=data["lib"], version=data["version"], config=data.get("config"))

    def to_dict(self) -> dict[str, t.Any]:
        return {"family": self.family, "lib": self.lib, "version": self.version, "config": self.config}


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
        lib: types.ModelLib | None = None,
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
    capabilities: ModelCapabilities | None = None
    extra: dict[str, t.Any] | None = None

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        family: types.ModelFamily,
        model_id: str | uuid.UUID | None,
        timestamp: datetime.datetime | None,
        params: dict[str, t.Any] | None,
        metrics: dict[str, t.Any] | None,
        extra: dict[str, t.Any] | None,
        capabilities: ModelCapabilities | None = None,
        config: dict[str, t.Any] | None = None,
        lib: types.ModelLib | None = None,
    ) -> "Metadata":
        serializer = ModelSerializer.from_lib(lib) if lib else ModelSerializer.from_model(model)
        return cls(
            id=model_id or uuid.uuid4(),
            timestamp=timestamp or datetime.datetime.now(),
            framework=FrameworkInfo.from_model(model, family=family, lib=lib, config=config),
            model=ModelInfo.from_model(model, params, metrics, lib=lib),
            capabilities=capabilities if capabilities is not None else serializer.detect_capabilities(model),
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
            capabilities=(ModelCapabilities.from_dict(data["capabilities"]) if data.get("capabilities") else None),
            extra=data.get("extra"),
        )

    def to_dict(self) -> dict[str, t.Any]:
        out: dict[str, t.Any] = {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "framework": self.framework.to_dict(),
            "model": self.model.to_dict(),
            "extra": self.extra,
        }
        if self.capabilities is not None:
            out["capabilities"] = self.capabilities.to_dict()
        return out


Artifacts = dict[str, str | os.PathLike | pathlib.Path]


@dataclasses.dataclass(frozen=True)
class ModelArtifact:
    """ML Model wrapper to provide mechanisms for serialization and deserialization using Flama format.

    Holds the wire-level :attr:`source` (raw bytes or extracted directory path) and materialises the
    live model lazily through the :attr:`model` cached property. Dispatch on first access is
    family-aware: ``family == "llm"`` returns the source path verbatim (the LLM backends consume the
    directory directly); ``family == "ml"`` calls the framework-specific
    :class:`~flama.serialize.model_serializers.base.BaseModelSerializer` to materialise an in-memory
    model object.

    The :attr:`directory` field carries the lifetime of a :class:`ModelDirectory` extracted during
    deserialization; it is excluded from equality, hashing and ``repr`` because it is a runtime
    resource, not part of the model identity.
    """

    meta: Metadata
    artifacts: Artifacts | None = None
    directory: ModelDirectory | None = dataclasses.field(default=None, repr=False, compare=False, hash=False)
    source: bytes | pathlib.Path | None = dataclasses.field(default=None, repr=False, compare=False, hash=False)

    @functools.cached_property
    def model(self) -> t.Any:
        """Materialise the model from :attr:`source` on first access; cached thereafter.

        For LLM artifacts the source path is returned verbatim (LLM backends consume the directory
        directly). For ML artifacts the framework-specific
        :meth:`~flama.serialize.model_serializers.base.BaseModelSerializer.load` is called with the
        source. Live model objects passed through :meth:`from_model` pre-seed the cache so this
        property returns the object as-is without invoking the serializer.

        :raises ApplicationError: If the artifact carries neither a source nor a pre-seeded live model.
        """
        if self.source is None:
            raise exceptions.ApplicationError("Artifact has no source bound and no live model pre-seeded")
        if self.meta.framework.family == "llm":
            return self.source
        load_kwargs: dict[str, t.Any] = {"capabilities": self.meta.capabilities}
        if self.meta.framework.config:
            load_kwargs.update(self.meta.framework.config)
        return ModelSerializer.from_lib(self.meta.framework.lib).load(self.source, **load_kwargs)

    @classmethod
    def from_model(
        cls,
        model: t.Any,
        *,
        family: types.ModelFamily,
        model_id: str | uuid.UUID | None = None,
        timestamp: datetime.datetime | None = None,
        params: dict[str, t.Any] | None = None,
        metrics: dict[str, t.Any] | None = None,
        extra: dict[str, t.Any] | None = None,
        capabilities: ModelCapabilities | None = None,
        config: dict[str, t.Any] | None = None,
        artifacts: Artifacts | None = None,
        lib: types.ModelLib | None = None,
    ) -> "ModelArtifact":
        """Build a dump-side :class:`ModelArtifact` from a live model object or directory path.

        Path inputs are stored as :attr:`source` so the lazy property materialises them naturally on
        access. Live object inputs (already-loaded estimators, pipelines, etc.) are pre-seeded into
        :attr:`model`'s cache slot via ``__dict__`` so they bypass the serializer round-trip.
        """
        source: bytes | pathlib.Path | None = model if isinstance(model, pathlib.Path) else None
        instance = cls(
            meta=Metadata.from_model(
                model,
                family=family,
                model_id=model_id,
                timestamp=timestamp,
                params=params,
                metrics=metrics,
                extra=extra,
                capabilities=capabilities,
                config=config,
                lib=lib,
            ),
            artifacts=artifacts,
            source=source,
        )
        if source is None:
            instance.__dict__["model"] = model
        return instance
