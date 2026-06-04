import functools
import pathlib
import typing as t
import uuid
import weakref

from flama import exceptions
from flama.models.engine.backend.llm.base import TransformerLLMBackend
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.serialize.data_structures import LLMModelCapabilities

try:
    import vllm
    from transformers import AutoProcessor
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.sampling_params import RequestOutputKind
except Exception:  # pragma: no cover
    vllm = None
    AutoProcessor = None
    AsyncEngineArgs = None
    RequestOutputKind = None

__all__ = ["VLLMBackend"]


class VLLMBackend(TransformerLLMBackend):
    """LLM backend backed by :class:`vllm.AsyncLLMEngine` (Linux/CUDA).

    The backend constructs the vLLM engine itself from the extracted HuggingFace model directory
    so the protocol layer never imports vLLM. Construction is delegated to
    :meth:`vllm.AsyncLLMEngine.from_engine_args`; *engine_params* are forwarded verbatim into
    :class:`vllm.engine.arg_utils.AsyncEngineArgs`. The engine's ``shutdown`` method is wired to
    a :class:`weakref.finalize` so the underlying compute resources are released when the
    backend is collected.

    Multimodal inputs are supported when the engine wraps a vision- or audio-capable model: the
    bound HuggingFace :class:`~transformers.AutoProcessor` handles chat-template alignment
    between text tokens and image / audio placeholders, and :attr:`capabilities` translates the
    resolved processor's sub-attributes into the matching
    :class:`~flama.serialize.data_structures.LLMModelCapabilities`.

    :param model_dir: Path to the extracted HuggingFace model directory.
    :param capabilities: Optional override; defaults to a runtime-detected
        :class:`LLMModelCapabilities`.
    :param engine_params: Extra keyword arguments forwarded to :class:`AsyncEngineArgs`.
    """

    @classmethod
    def runnable(cls) -> bool:
        """Return ``True`` when ``vllm`` is importable on the host."""
        return vllm is not None and AsyncEngineArgs is not None

    def __init__(
        self,
        model_dir: pathlib.Path,
        /,
        *,
        capabilities: LLMModelCapabilities | None = None,
        **engine_params: t.Any,
    ) -> None:
        if vllm is None or AsyncEngineArgs is None:  # noqa
            raise exceptions.FrameworkNotInstalled("vllm")

        engine = vllm.AsyncLLMEngine.from_engine_args(
            AsyncEngineArgs(model=str(model_dir), disable_log_stats=True, **engine_params)
        )
        super().__init__(engine)
        self._model_dir = pathlib.Path(model_dir)
        if capabilities is not None:
            self.__dict__["capabilities"] = capabilities
        if hasattr(engine, "shutdown"):
            weakref.finalize(self, engine.shutdown)

    @staticmethod
    def _is_multimodal_processor(candidate: t.Any) -> bool:
        """Return ``True`` when *candidate* exposes any of the multimodal sub-processor attributes."""
        return any(hasattr(candidate, attr) for attr in ("image_processor", "feature_extractor", "audio_processor"))

    @functools.cached_property
    def capabilities(self) -> LLMModelCapabilities:
        renderer = self._renderer
        return LLMModelCapabilities(
            text=True,
            image=hasattr(renderer, "image_processor"),
            audio=hasattr(renderer, "feature_extractor") or hasattr(renderer, "audio_processor"),
        )

    @functools.cached_property
    def _tokenizer(self) -> t.Any:
        """Return the underlying HuggingFace tokenizer used by the vLLM engine.

        vLLM exposes the tokenizer via ``engine.tokenizer.tokenizer``; resolved once and cached
        for the rest of the backend's lifetime.
        """
        tokenizer_group = getattr(self.model, "tokenizer", None)
        return getattr(tokenizer_group, "tokenizer", tokenizer_group)

    def _max_context(self) -> int | None:
        """Probe the vLLM engine for the resolved ``max_model_len``.

        vLLM stores it on ``engine.engine.model_config`` (the ``AsyncLLMEngine`` wraps an inner
        engine that owns the resolved :class:`vllm.config.ModelConfig`); older releases hung it
        directly on ``engine.model_config``. The probe walks both paths and only accepts positive
        integers — mocked engines in tests substitute :class:`unittest.mock.Mock` for these
        attributes, so the type guard prevents a truthy ``Mock`` from poisoning the resolver.
        """
        config = getattr(getattr(self.model, "engine", None), "model_config", None) or getattr(
            self.model, "model_config", None
        )
        value = getattr(config, "max_model_len", None) if config is not None else None
        return value if isinstance(value, int) and value > 0 else None

    @functools.cached_property
    def _renderer(self) -> t.Any:
        """Resolve the HuggingFace ``AutoProcessor`` for this engine, falling back to the bare tokenizer.

        Tries the vLLM-internal hook first (some engine versions expose the HF processor as
        ``engine.processor``), then attempts ``AutoProcessor.from_pretrained`` on the engine's
        model path. Any failure (missing processor config, ``transformers`` unable to detect a
        vision class) falls back to :attr:`_tokenizer` so the text-only path keeps working.
        """
        if (candidate := getattr(self.model, "processor", None)) is not None and self._is_multimodal_processor(
            candidate
        ):
            return candidate

        if AutoProcessor is None:  # pragma: no cover
            return self._tokenizer

        try:
            processor = AutoProcessor.from_pretrained(str(self._model_dir), trust_remote_code=True)
        except Exception:  # pragma: no cover
            return self._tokenizer

        return processor if self._is_multimodal_processor(processor) else self._tokenizer

    async def generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
        """Yield deltas from the vLLM async engine for an already-tokenised prompt.

        Uses :data:`~vllm.sampling_params.RequestOutputKind.DELTA` so each iteration yields only
        the newly generated tokens. Token IDs are passed via ``prompt_token_ids`` so vLLM does
        not re-tokenize. When *inputs* carries decoded multimodal payloads (vision / audio
        models) they are reassembled into vLLM's ``multi_modal_data`` dict and forwarded.
        Per-step token counts come from ``token_ids`` on the delta output; ``finish_reason``
        is propagated verbatim from vLLM on the final delta.

        :param inputs: Engine-ready :class:`EngineInput` (token IDs plus optional decoded
            multimodal payloads).
        :param params: Sampling parameters forwarded to :class:`vllm.SamplingParams`.
        :return: Async iterator of :class:`EngineDelta`.
        :raises FrameworkNotInstalled: If vllm is not installed.
        """
        if vllm is None or RequestOutputKind is None:  # noqa
            raise exceptions.FrameworkNotInstalled("vllm")

        max_tokens = self._resolve_max_tokens(params, len(inputs.tokens))

        engine_inputs: dict[str, t.Any] = {"prompt_token_ids": inputs.tokens}
        multi_modal_data: dict[str, list[t.Any]] = {}
        if inputs.images:
            multi_modal_data["image"] = list(inputs.images)
        if inputs.audios:
            multi_modal_data["audio"] = list(inputs.audios)
        if multi_modal_data:
            engine_inputs["multi_modal_data"] = multi_modal_data

        async for x in self.model.generate(
            engine_inputs,
            vllm.SamplingParams(max_tokens=max_tokens, **params, output_kind=RequestOutputKind.DELTA),
            str(uuid.uuid4()),
        ):
            output = x.outputs[0]
            text = output.text or ""
            finish_reason = getattr(output, "finish_reason", None)
            if text or finish_reason is not None:
                yield EngineDelta(
                    text=text, token_count=len(getattr(output, "token_ids") or []), finish_reason=finish_reason
                )
