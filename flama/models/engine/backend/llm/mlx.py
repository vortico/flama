import concurrent.futures
import contextlib
import dataclasses
import functools
import os
import pathlib
import typing as t

from flama import concurrency, exceptions
from flama.models.engine.backend.llm._base import TransformerLLMBackend
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.serialize.data_structures import LLMModelCapabilities
from flama.serialize.exceptions import UnknownModelCapabilities
from flama.serialize.model_serializers import ModelSerializer

# HACK: silence ``mlx_vlm.generate`` chunked-prefill ``tqdm`` bar (line 1304 of
# ``mlx_vlm/generate.py`` instantiates ``tqdm(total=..., desc="Prefill", unit="tok")`` with no
# ``disable`` kwarg). Two-step belt-and-braces: (1) set ``TQDM_DISABLE=1`` around the
# ``mlx_lm`` / ``mlx_vlm`` imports so ``tqdm`` snapshots ``disable=True`` into the partialmethod
# keyword defaults at ``@envwrap`` decoration time when ``mlx_lm`` / ``mlx_vlm`` are the first
# transitive importers; (2) post-hoc, rebuild ``tqdm.std.tqdm.__init__``'s partialmethod with
# ``disable=True`` baked in so the snapshot lands even if some earlier importer (``torch.hub``
# in tests, ``transformers`` in some deployments) already captured the env var when it was
# unset. Either path leaves explicit ``disable=False`` callers untouched (keyword override
# wins). Replace with a proper opt-in once ``mlx_vlm`` exposes a ``progress=False`` (or
# equivalent) kwarg on :func:`mlx_vlm.stream_generate`.
_TQDM_DISABLE_PRESET = os.environ.get("TQDM_DISABLE")
os.environ["TQDM_DISABLE"] = "1"
try:
    try:
        import mlx.core as mx
        from mlx_lm import load as mlx_lm_load
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
    except Exception:  # pragma: no cover
        mx = None
        mlx_lm_load = None
        stream_generate = None
        make_sampler = None

    try:
        from mlx_vlm import load as mlx_vlm_load
        from mlx_vlm import stream_generate as mlx_vlm_stream_generate
    except Exception:  # pragma: no cover
        mlx_vlm_load = None
        mlx_vlm_stream_generate = None
finally:
    if _TQDM_DISABLE_PRESET is None:
        os.environ.pop("TQDM_DISABLE", None)
    else:
        os.environ["TQDM_DISABLE"] = _TQDM_DISABLE_PRESET

try:
    from tqdm.std import tqdm as _Tqdm

    _init = _Tqdm.__dict__.get("__init__")
    if isinstance(_init, functools.partialmethod) and _init.keywords.get("disable") is not True:
        _Tqdm.__init__ = functools.partialmethod(  # ty: ignore[invalid-assignment]
            _init.func, *_init.args, **{**_init.keywords, "disable": True}
        )
    del _init, _Tqdm
except Exception:  # pragma: no cover - tqdm not installed
    pass

__all__ = ["MLXBackend", "MlxRuntime"]


class _MlxStreamResp(t.Protocol):
    """Shape of items yielded by :func:`mlx_lm.stream_generate` and :func:`mlx_vlm.stream_generate`.

    ``text`` is the newly decoded text fragment for the step. ``generation_tokens`` (when
    exposed by recent ``mlx_vlm`` releases) is the running total of tokens generated so far —
    the per-step count is the diff against the previous chunk's value. ``finish_reason`` is set
    on the terminal response by recent releases of both runtimes (``"stop"`` / ``"length"``);
    older versions omit the attribute.
    """

    text: str


@dataclasses.dataclass(frozen=True)
class MlxRuntime:
    """MLX runtime bundle owned by :class:`MLXBackend`.

    A single container covers both text-only (``mlx-lm.load``) and multimodal
    (``mlx-vlm.load``) runtimes: text runtimes leave :attr:`processor` as :data:`None`, while
    multimodal runtimes attach the HuggingFace :class:`~transformers.AutoProcessor` that owns
    the tokenizer plus image / audio preprocessors and renders ``apply_chat_template`` for
    multimodal inputs. The :attr:`capabilities` mirror the value resolved at construction time
    so :class:`MLXBackend` can lift them straight into its instance state without re-probing.

    :param model: The MLX model object (text or multimodal).
    :param tokenizer: The HuggingFace tokenizer (always present).
    :param processor: The HuggingFace ``AutoProcessor`` for multimodal runtimes, or :data:`None`
        for text-only ones.
    :param capabilities: Modal capabilities resolved at construction time.
    """

    model: t.Any
    tokenizer: t.Any
    processor: t.Any = None
    capabilities: LLMModelCapabilities = dataclasses.field(default_factory=LLMModelCapabilities)


class MLXBackend(TransformerLLMBackend):
    """LLM backend backed by MLX for macOS / Apple Silicon.

    The backend builds its own :class:`MlxRuntime` from the extracted HuggingFace model
    directory so the protocol layer never imports MLX. Dispatch keys off
    :attr:`capabilities.is_multimodal`: text-only models go through :func:`mlx_lm.load` /
    :func:`mlx_lm.stream_generate`; multimodal models (vision, audio, or both) go through
    :func:`mlx_vlm.load` / :func:`mlx_vlm.stream_generate` and carry the bound
    :class:`~transformers.AutoProcessor`.

    Capability resolution: when *capabilities* is provided (typically read from the
    ``.flm`` manifest) it is used verbatim; otherwise the backend falls back to the
    transformers serializer's
    :meth:`~flama.serialize.model_serializers.transformers.ModelSerializer.detect_capabilities`
    probe against the extracted bundle. When neither source yields a populated capabilities
    instance, :class:`~flama.serialize.exceptions.UnknownModelCapabilities` is raised.

    :param model_dir: Path to the extracted HuggingFace model directory.
    :param capabilities: Optional override read from the artifact manifest; falls back to the
        transformers serializer probe when omitted.
    :param engine_params: Reserved for forward-compatibility; currently unused.
    :raises FrameworkNotInstalled: If ``mlx-lm`` (text-only) or ``mlx-vlm`` (multimodal) is not installed.
    :raises UnknownModelCapabilities: If capabilities cannot be resolved from either source.
    """

    DEFAULT_TEMP: t.ClassVar[float] = 0.0

    @classmethod
    def runnable(cls) -> bool:
        """Return ``True`` when ``mlx-lm`` is importable on the host."""
        return mx is not None and mlx_lm_load is not None

    def __init__(
        self,
        model_dir: pathlib.Path,
        /,
        *,
        capabilities: LLMModelCapabilities | None = None,
        **engine_params: t.Any,
    ) -> None:
        resolved = capabilities or ModelSerializer.from_lib("transformers").detect_capabilities(model_dir)
        if not isinstance(resolved, LLMModelCapabilities):
            raise UnknownModelCapabilities(str(model_dir))

        # MLX binds its Metal/CUDA stream to whichever OS thread first allocates an array, so every
        # subsequent operation on that array must come from the same thread or MLX raises
        # ``RuntimeError: There is no Stream(gpu, ...)`` (most visible on the mlx_vlm path that asyncs
        # eval mid-step). The backend therefore owns a dedicated single-worker executor and routes
        # the model load - and every later `generate` call - through it.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx-backend")
        runtime = self._executor.submit(self._load_runtime, model_dir, resolved).result()

        super().__init__(runtime)

    @staticmethod
    def _load_runtime(model_dir: pathlib.Path, capabilities: LLMModelCapabilities) -> "MlxRuntime":
        if capabilities.is_multimodal:
            if mlx_vlm_load is None:  # noqa
                raise exceptions.FrameworkNotInstalled("mlx-vlm")
            vlm_model, processor = mlx_vlm_load(str(model_dir))
            return MlxRuntime(
                model=vlm_model, tokenizer=processor.tokenizer, processor=processor, capabilities=capabilities
            )
        if mlx_lm_load is None:  # noqa
            raise exceptions.FrameworkNotInstalled("mlx-lm")
        lm_model, tokenizer = mlx_lm_load(str(model_dir))
        return MlxRuntime(model=lm_model, tokenizer=tokenizer, capabilities=capabilities)

    @functools.cached_property
    def capabilities(self) -> LLMModelCapabilities:
        return self.model.capabilities

    @functools.cached_property
    def _tokenizer(self) -> t.Any:
        """Return the underlying HuggingFace tokenizer carried by the MLX runtime."""
        return self.model.tokenizer

    @functools.cached_property
    def _renderer(self) -> t.Any:
        return self.model.processor if self.capabilities.is_multimodal else self._tokenizer

    def _max_context(self) -> int | None:
        """Probe the MLX runtime for the model's max context length.

        mlx-lm exposes the value on ``model.args`` (the dataclass mirroring ``config.json``);
        mlx-vlm carries it on ``model.config`` (sometimes nested under ``text_config`` for
        joint-vision-language models). Each candidate is type-checked because mocked runtimes
        in tests substitute :class:`unittest.mock.Mock` for these attributes — accepting only
        positive integers keeps the probe honest. ``model_max_length`` on HuggingFace tokenizers
        sometimes carries a sentinel ``int(1e30)`` meaning "not configured"; we discard that.
        """
        model = self.model.model
        candidates = (
            getattr(model, "args", None),
            getattr(getattr(model, "config", None), "text_config", None),
            getattr(model, "config", None),
        )
        for source in candidates:
            value = getattr(source, "max_position_embeddings", None) if source is not None else None
            if isinstance(value, int) and value > 0:
                return value
        value = getattr(self._tokenizer, "model_max_length", None)
        if isinstance(value, int) and 0 < value < 1_000_000:
            return value
        return None

    def _build_mlx_vlm_extras(self, inputs: EngineInput) -> dict[str, t.Any]:
        """Build the ``input_ids`` / multimodal-feature kwargs for the ``mlx_vlm.stream_generate`` bypass.

        The pre-tokenised prompt is wrapped as a single-row :class:`mlx.core.array` and forwarded as
        ``input_ids``. Decoded images and audios, when present, are rendered through the bound
        :class:`~transformers.AutoProcessor` so the model receives the same auxiliary tensors
        (``pixel_values``, ``input_features``, masks, ...) that :func:`mlx_vlm.prepare_inputs` would
        have produced - only the processor's own ``input_ids`` / ``attention_mask`` are dropped to
        avoid clashing with the pre-tokenised ids.

        :param inputs: Engine-ready :class:`EngineInput` carrying token IDs and optional decoded
            multimodal payloads.
        :return: Mapping merged into the ``mlx_vlm.stream_generate`` call.
        """
        # ``mx`` is the optional ``mlx.core`` module (``None`` only when mlx is not installed); this
        # backend is reached exclusively when mlx is available, so ``mx`` is non-None here.
        extras: dict[str, t.Any] = {"input_ids": mx.array([inputs.tokens])}  # ty: ignore[unresolved-attribute]
        if not (inputs.images or inputs.audios):
            return extras
        proc_kwargs: dict[str, t.Any] = {"text": "", "return_tensors": "mlx", "add_special_tokens": False}
        if inputs.images:
            proc_kwargs["images"] = list(inputs.images)
        if inputs.audios:
            proc_kwargs["audio"] = list(inputs.audios)
        processed = self.model.processor(**proc_kwargs)
        extras.update({k: v for k, v in processed.items() if k not in {"input_ids", "attention_mask"}})
        return extras

    async def generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
        """Yield deltas from the synchronous MLX generator.

        Bridges :func:`mlx_lm.stream_generate` (text runtime) or :func:`mlx_vlm.stream_generate`
        (multimodal runtime) into an async iterator via :func:`flama.concurrency.iterate` pinned
        to :attr:`_executor` - MLX binds its Metal/CUDA stream to whichever thread first
        allocates an array, so every step has to run on the same worker the model was loaded
        on or MLX raises ``no Stream(gpu, 1) in current thread``. Token IDs are passed straight
        through so MLX does not re-tokenize. For multimodal runtimes the call goes through the
        documented ``input_ids`` bypass of :func:`mlx_vlm.stream_generate` - feeding pre-tokenised
        ``list[int]`` through ``prompt`` (which is typed ``str``) would otherwise be coerced into
        ``list[str]`` by the HuggingFace tokenizer, inflating the batch dimension and corrupting
        the KV cache. Any decoded PIL images and ``(numpy_waveform, sample_rate)`` tuples are
        rendered through the bound :class:`~transformers.AutoProcessor` and forwarded as
        ``pixel_values`` / audio kwargs alongside the pre-tokenised ``input_ids``.

        Per-step token counts are runtime-specific. ``mlx_lm.stream_generate`` yields exactly one
        decoded token per chunk, so :attr:`EngineDelta.token_count` is reported as ``1`` for any
        chunk carrying text. ``mlx_vlm.stream_generate`` may yield multi-token chunks (chunked
        prefill / batched decoding); when the chunk exposes a cumulative ``generation_tokens``
        the per-step count is the diff against the previous chunk's value, otherwise the count
        is recovered by encoding the chunk's text through :attr:`MlxRuntime.tokenizer`.
        :attr:`EngineDelta.finish_reason` is propagated when the runtime sets it on the terminal
        response (``mlx_lm >= 0.20`` and recent ``mlx_vlm`` use ``"stop"`` / ``"length"``); older
        releases omit the attribute and the field stays :data:`None`.

        :param inputs: Engine-ready :class:`EngineInput` (token IDs plus optional decoded
            multimodal payloads).
        :param params: Generation parameters merged into the MLX call.
        :return: Async iterator of :class:`EngineDelta`.
        :raises FrameworkNotInstalled: If mlx-lm (text) or mlx-vlm (multimodal) is not installed.
        """
        if make_sampler is None:  # noqa
            raise exceptions.FrameworkNotInstalled("mlx-lm")

        max_tokens = self._resolve_max_tokens(params, len(inputs.tokens))
        sampler = make_sampler(temp=params.pop("temperature", self.DEFAULT_TEMP))

        if self.capabilities.is_multimodal:
            if mlx_vlm_stream_generate is None or mx is None:  # noqa
                raise exceptions.FrameworkNotInstalled("mlx-vlm")
            source: t.Iterator[_MlxStreamResp] = mlx_vlm_stream_generate(
                self.model.model,
                self.model.processor,
                prompt="",
                max_tokens=max_tokens,
                sampler=sampler,
                **self._build_mlx_vlm_extras(inputs),
            )
        else:
            if stream_generate is None:  # noqa
                raise exceptions.FrameworkNotInstalled("mlx-lm")
            source = stream_generate(
                self.model.model,
                self.model.tokenizer,
                prompt=inputs.tokens,
                max_tokens=max_tokens,
                sampler=sampler,
            )

        is_vlm = self.capabilities.is_multimodal
        previous_total = 0
        async with contextlib.aclosing(concurrency.iterate(source, executor=self._executor)) as items:
            async for chunk in items:
                text = chunk.text or ""
                finish_reason = getattr(chunk, "finish_reason", None)
                if not text and finish_reason is None:
                    continue
                if is_vlm:
                    total = getattr(chunk, "generation_tokens", None)
                    if isinstance(total, int) and total >= previous_total:
                        token_count: int | None = total - previous_total
                        previous_total = total
                    elif text:
                        token_count = len(self.model.tokenizer.encode(text, add_special_tokens=False))
                    else:
                        token_count = None
                else:
                    token_count = 1 if text else None
                yield EngineDelta(text=text, token_count=token_count, finish_reason=finish_reason)
