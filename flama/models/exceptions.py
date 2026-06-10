import typing as t

from flama.exceptions import ApplicationError

__all__ = ["ModelError", "LLMUnsupportedContentPart", "LLMUnsupportedCapability", "LLMGenerationError"]


class ModelError(ApplicationError):
    """Base class for runtime errors raised by the model layer.

    Inherits :class:`~flama.exceptions.ApplicationError` so model errors participate in the
    framework-wide hierarchy alongside :class:`~flama.exceptions.DependencyNotInstalled` and
    :class:`~flama.exceptions.SQLAlchemyError`. Concrete subclasses encode specific request- or
    capability-level invariants that the model layer enforces against caller input.
    """

    ...


class LLMUnsupportedContentPart(ModelError):
    """A structured-content message references a content-part type the current layer does not accept.

    Raised by each serving's
    :meth:`~flama.models.resources.serving.llm._base.LLMServing.parse` when an incoming
    message carries a ``type`` outside the layer's accepted wire vocabulary (for instance
    ``audio:url`` against the Ollama serving path).
    """

    def __init__(self, kind: str, allowed: t.Iterable[str]) -> None:
        self.kind = kind
        self.allowed = sorted(allowed)
        super().__init__(f"Wrong content part type '{kind}', expected one of: {self.allowed}")


class LLMUnsupportedCapability(ModelError):
    """A multimodal request asked for a modality the loaded model does not advertise.

    Raised by :meth:`~flama.models.engine.backend.llm._base.LLMBackend.prepare_input` when a
    structured-content message references an image or audio fragment but the backend's
    :class:`~flama.serialize.data_structures.LLMModelCapabilities` does not flag the matching
    modality.
    """

    def __init__(self, modality: str) -> None:
        self.modality = modality
        super().__init__(f"Model does not support {modality} input")


class LLMGenerationError(ModelError):
    """Generation failed mid-stream while assembling a buffered envelope.

    Raised by :meth:`~flama.models.wire.dialect._base.Dialect.assemble` when the source stream's terminal
    :class:`~flama.models.StopEvent` carries ``stop_reason="error"``. Streaming paths surface this same
    failure through dialect-specific wire frames (:class:`~flama.models.wire.dialect.llm.native.ErrorEvent`,
    :class:`~flama.models.wire.dialect.llm.openai.ErrorChunk`,
    :class:`~flama.models.wire.dialect.llm.ollama.ErrorChunk`); the buffered path has no in-band signal so it
    raises this exception which the serving layer translates to ``HTTPException(500)``.
    """

    def __init__(self, detail: str = "LLM stream generation failed") -> None:
        self.detail = detail
        super().__init__(detail)
