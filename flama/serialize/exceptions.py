from flama.exceptions import ApplicationError

__all__ = [
    "ModelArtifactError",
    "UnknownCompression",
    "UnknownModelCapabilities",
    "UnknownModelKind",
    "UnsupportedProtocol",
]


class ModelArtifactError(ApplicationError):
    """Base class for model-artifact deserialisation invariants.

    Inherits :class:`~flama.exceptions.ApplicationError` so artifact errors participate in the
    framework-wide error hierarchy alongside :class:`~flama.exceptions.DependencyNotInstalled`,
    :class:`~flama.exceptions.SQLAlchemyError`, etc. Concrete subclasses surface specific failure
    modes (unknown capabilities, malformed manifest, ...).
    """

    def __init__(self, name: str, msg: str = "is invalid") -> None:
        self.name = name
        super().__init__(f"{name} {msg}")


class UnknownModelCapabilities(ModelArtifactError):
    """The serializer cannot resolve model capabilities from the manifest or on-disk inspection.

    Raised by capability-aware serializers (notably MLX / vLLM) when neither the artifact's
    manifest nor a disk-side probe yields a populated :class:`~flama.serialize.data_structures.ModelCapabilities`,
    because dispatch (text-only vs multimodal runtime) cannot be safely chosen.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name, "has no capabilities advertised in the manifest or on disk")


class UnknownModelKind(ModelArtifactError):
    """The model section in a v2 ``.flm`` body carries a ``kind`` byte the reader does not recognise.

    Raised by :class:`~flama.serialize.protocols.v2.Protocol` when the model section's discriminator
    is outside the supported range (currently ``binary`` and ``bundle``). Reserved or vendor values
    are rejected so a partial/legacy reader never silently mis-routes the payload.
    """

    def __init__(self, value: int) -> None:
        super().__init__(f"0x{value:02x}", "is not a known model kind")


class UnknownCompression(ModelArtifactError):
    """A compression discriminator does not map to a known codec.

    Raised by the serialisation layer whenever a compression value cannot be resolved. Three
    classes of failure share this exception:

    - User-supplied codec name at dump time (e.g. ``compression="zstd"``) routed through
      :class:`~flama.serialize.serializer.Serializer`.
    - File-level compression byte read from the outer ``.flm`` header by
      :meth:`~flama.serialize.serializer.Serializer.load` /
      :meth:`~flama.serialize.serializer.Serializer.meta` /
      :meth:`~flama.serialize.serializer.Serializer.manifest`.
    - Per-section compression byte read from the body of a v2 dump by
      :class:`~flama.serialize.protocols.v2.Protocol` (``inherit`` falls back to the file-level
      compression; ``none`` and the named codecs pass through; every other byte is rejected).

    Vendor-coded, reserved, or corrupted values surface immediately instead of being silently
    mis-decoded. The original :attr:`value` (int byte or string name) is preserved for
    diagnostics.
    """

    def __init__(self, value: int | str) -> None:
        self.value = value
        rendered = f"0x{value:02x}" if isinstance(value, int) and value >= 0 else repr(value)
        super().__init__(rendered, "is not a known compression format")


class UnsupportedProtocol(ModelArtifactError):
    """The requested serialization protocol cannot represent this artifact.

    Raised at pack time when :class:`~flama.serialize.protocols.base.BaseProtocol` is asked to
    write an artifact whose source / manifest combination has no representation in the chosen
    version's wire format:

    - :class:`~flama.serialize.protocols.v1.Protocol` is binary-only — :class:`pathlib.Path`
      sources (directory bundles) require :class:`~flama.serialize.protocols.v2.Protocol`,
      which carries an explicit kind byte (see :data:`~flama.types.SerializationModelKind`).
    - :class:`~flama.serialize.protocols.v2.Protocol` rejects mismatched kind / source pairs
      (e.g. a binary-kind ML model with a directory source).

    Distinct from the ``ValueError`` raised by
    :meth:`~flama.serialize.protocols.base.Protocol.from_version` for unknown version numbers:
    that signals "version X does not exist", this signals "version X exists but does not support
    this artifact".
    """

    def __init__(self, *, protocol: int, reason: str) -> None:
        self.protocol = protocol
        self.reason = reason
        super().__init__(f"protocol v{protocol}", f"does not support: {reason}")
