import typing as t

from flama.exceptions import ApplicationError

__all__ = [
    "ModelError",
    "LLMUnsupportedContentPart",
    "LLMUnsupportedCapability",
    "LLMGenerationError",
    "LLMEmptyGeneration",
    "LLMUnsupportedModel",
]


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


class LLMUnsupportedModel(ModelError):
    """No installed LLM runtime could load the model.

    Raised by :meth:`~flama.models.engine.backend.llm._base.LLMBackend.from_model_artifact` when every
    runtime it tried refused the artifact. The reasons are runtime-specific and numerous — an
    architecture absent from the runtime's registry, weights that fail a strict load, an unsupported
    quantization — and each runtime words them differently, so this exception deliberately reports only
    the observable outcome and defers the diagnosis to the chained cause.

    Read ``__cause__`` for the failure of the last runtime attempted; where a backend tries more than
    one (MLX falls back between mlx-lm and mlx-vlm), the earlier failures are logged as they happen.

    A missing runtime is not this error: an uninstallable dependency surfaces as
    :class:`~flama.exceptions.FrameworkNotInstalled`, and an artifact whose capabilities cannot be
    resolved as :class:`~flama.serialize.exceptions.UnknownModelCapabilities`. Both pass through
    untouched so they stay distinguishable from a model the runtimes simply cannot build.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No installed LLM runtime could load the model at '{name}'")


class LLMEmptyGeneration(ModelError):
    """The engine ran to completion without emitting a single text fragment or tool call.

    Raised by :meth:`~flama.models.LLMModel.query` when the decoded block list carries no
    :class:`~flama.models.TextEvent` or :class:`~flama.models.ToolEvent`. The model itself did not
    fail — it read the prompt and had nothing to add — so the cause is almost always upstream of
    generation, in how the conversation was rendered.

    By far the most common cause is a chat template that ends the rendered prompt on a *closed*
    turn, leaving the model no opening to speak. Templates disagree on where an assistant turn's
    text belongs when that turn also carries tool calls: most emit it before the call, but some
    (notably the Gemma 4 family) emit it after the tool result and then close the turn, which reads
    as a finished conversation. That specific shape is detected and compensated for by
    :attr:`~flama.models.engine.backend.llm._base.TransformerLLMBackend._wrong_tool_narration`, which
    warns once per model when it engages; a template that ends a prompt prematurely for any other
    reason surfaces here instead.
    """

    def __init__(self, detail: str = "LLM engine produced no output") -> None:
        self.detail = detail
        super().__init__(detail)
