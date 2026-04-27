import typing as t
import uuid
import weakref

from flama import exceptions
from flama.concurrency import run
from flama.models.base import BaseLLMModel

try:
    import vllm
    from vllm.sampling_params import RequestOutputKind
except Exception:  # pragma: no cover
    vllm = None
    RequestOutputKind = None

try:
    from mlx_lm import stream_generate  # ty: ignore[unresolved-import]
    from mlx_lm.sample_utils import make_sampler  # ty: ignore[unresolved-import]
    from vllm_metal.model_runner import MetalModelRunner  # ty: ignore[unresolved-import]
except Exception:  # pragma: no cover
    MetalModelRunner = None
    stream_generate = None
    make_sampler = None

__all__ = ["CudaModel", "MetalModel"]


class _MlxStreamResp(t.Protocol):
    """Shape of items yielded by :func:`mlx_lm.stream_generate`."""

    text: str


class CudaModel(BaseLLMModel):
    """vLLM large-language-model wrapper for standard vLLM (Linux/CUDA).

    Expects ``self.model`` to be a ready-to-use :class:`vllm.AsyncLLMEngine`.
    """

    def __init__(self, model: t.Any, meta: t.Any, artifacts: t.Any):
        super().__init__(model, meta, artifacts)
        if hasattr(model, "shutdown"):
            weakref.finalize(self, model.shutdown)

    async def _tokens(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[str]:
        """Yield text deltas from the vLLM async engine.

        Uses :data:`~vllm.sampling_params.RequestOutputKind.DELTA` so each iteration yields only the newly generated
        tokens since the previous step.

        :param prompt: The input prompt.
        :param params: Override generation parameters merged with defaults.
        :return: Async iterator of text deltas.
        """
        if vllm is None or RequestOutputKind is None:  # noqa
            raise exceptions.FrameworkNotInstalled("vllm")

        async for output in self.model.generate(
            prompt,
            vllm.SamplingParams(**{**self.params, **params}, output_kind=RequestOutputKind.DELTA),
            str(uuid.uuid4()),
        ):
            if text := output.outputs[0].text:
                yield text


class MetalModel(BaseLLMModel):
    """vLLM large-language-model wrapper for vllm-metal (macOS/Apple Silicon).

    Expects ``self.model`` to be a :class:`vllm_metal.model_runner.MetalModelRunner`.
    """

    async def _tokens(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[str]:
        """Yield text deltas from the synchronous MLX generator, one ``next`` per await.

        Bridges :func:`mlx_lm.stream_generate` (a sync generator) into an async iterator by running each ``next()``
        in the default thread pool via :func:`flama.concurrency.run`. No producer task or queue required.

        :param prompt: The input prompt.
        :param params: Override generation parameters merged with defaults.
        :return: Async iterator of text deltas.
        """
        if stream_generate is None or make_sampler is None:  # noqa
            raise exceptions.FrameworkNotInstalled("vllm-metal")

        base_params = {**self.params, **params}
        gen_params = {
            "max_tokens": base_params.pop("max_tokens", base_params.pop("max_new_tokens", 256)),
            "sampler": make_sampler(temp=base_params.pop("temperature", 0.0)),
        }
        iterator: t.Iterator[_MlxStreamResp] = iter(
            stream_generate(self.model.model, self.model.tokenizer, prompt=prompt, **gen_params)
        )

        def _step() -> _MlxStreamResp | None:
            return next(iterator, None)

        while (chunk := await run(_step)) is not None:
            if chunk.text:
                yield chunk.text
