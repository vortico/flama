import asyncio
import queue
import typing as t
import uuid
import weakref

from flama import exceptions
from flama.models.base import BaseLLMModel

try:
    import vllm
    from vllm.sampling_params import RequestOutputKind
except Exception:  # pragma: no cover
    vllm = None
    RequestOutputKind = None

try:
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import make_sampler
    from vllm_metal.model_runner import MetalModelRunner
except Exception:  # pragma: no cover
    MetalModelRunner = None
    stream_generate = None
    make_sampler = None

__all__ = ["CudaModel", "MetalModel"]


class CudaModel(BaseLLMModel):
    """vLLM large-language-model wrapper for standard vLLM (Linux/CUDA).

    Expects ``self.model`` to be a ready-to-use :class:`vllm.AsyncLLMEngine`.
    """

    def __init__(self, model: t.Any, meta: t.Any, artifacts: t.Any):
        super().__init__(model, meta, artifacts)
        weakref.finalize(self, self._shutdown_engine, model)

    @staticmethod
    def _shutdown_engine(engine: t.Any) -> None:
        if hasattr(engine, "shutdown"):
            engine.shutdown()

    async def query(self, prompt: str, /, **params: t.Any) -> t.Any:
        """Generate a complete response for the given prompt.

        Uses :data:`~vllm.sampling_params.RequestOutputKind.FINAL_ONLY` so the engine yields a single
        :class:`~vllm.RequestOutput` containing the full generated text.

        :param prompt: The input prompt.
        :param params: Override generation parameters merged with defaults.
        :return: The generated text.
        :raises HTTPException: 500 if the engine produces no output, 400 for any engine error.
        """
        if vllm is None or RequestOutputKind is None:  # noqa
            raise exceptions.FrameworkNotInstalled("vllm")

        try:
            result = await anext(
                aiter(
                    self.model.generate(
                        prompt,
                        vllm.SamplingParams(**{**self.params, **params}, output_kind=RequestOutputKind.FINAL_ONLY),
                        str(uuid.uuid4()),
                    )
                )
            )
            return result.outputs[0].text
        except StopAsyncIteration:
            raise exceptions.HTTPException(status_code=500, detail="vLLM engine produced no output")
        except Exception as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[t.Any]:
        """Stream output tokens for the given prompt.

        Uses :data:`~vllm.sampling_params.RequestOutputKind.DELTA` so each iteration yields only the newly generated
        tokens since the previous step.

        :param prompt: The input prompt.
        :param params: Override generation parameters merged with defaults.
        :return: Async iterator of output token strings.
        """
        if vllm is None or RequestOutputKind is None:  # noqa
            raise exceptions.FrameworkNotInstalled("vllm")

        async for output in self.model.generate(
            prompt,
            vllm.SamplingParams(**{**self.params, **params}, output_kind=RequestOutputKind.DELTA),
            str(uuid.uuid4()),
        ):
            try:
                if text := output.outputs[0].text:
                    yield text
            except Exception:
                return


class MetalModel(BaseLLMModel):
    """vLLM large-language-model wrapper for vllm-metal (macOS/Apple Silicon).

    Expects ``self.model`` to be a :class:`vllm_metal.model_runner.MetalModelRunner`.
    """

    def _generate_params(self, **params: t.Any) -> dict[str, t.Any]:
        merged = {**self.params, **params}
        return {
            "max_tokens": merged.pop("max_tokens", merged.pop("max_new_tokens", 256)),
            "sampler": make_sampler(temp=merged.pop("temperature", 0.0)),
        }

    async def query(self, prompt: str, /, **params: t.Any) -> t.Any:
        """Generate a complete response for the given prompt.

        Runs :func:`mlx_lm.stream_generate` in a thread to avoid blocking the event loop.

        :param prompt: The input prompt.
        :param params: Override generation parameters merged with defaults.
        :return: The generated text.
        :raises HTTPException: 400 for any engine error.
        """
        gen_params = self._generate_params(**params)

        def _sync() -> str:
            segments: list[str] = []
            for resp in stream_generate(self.model.model, self.model.tokenizer, prompt=prompt, **gen_params):
                segments.append(resp.text)
            return "".join(segments)

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[t.Any]:
        """Stream output tokens for the given prompt.

        A producer thread feeds tokens into a queue; the async iterator drains it.

        :param prompt: The input prompt.
        :param params: Override generation parameters merged with defaults.
        :return: Async iterator of output token strings.
        """
        gen_params = self._generate_params(**params)
        loop = asyncio.get_running_loop()
        q: queue.Queue[str | None] = queue.Queue()

        def _producer() -> None:
            try:
                for resp in stream_generate(self.model.model, self.model.tokenizer, prompt=prompt, **gen_params):
                    if resp.text:
                        q.put(resp.text)
            finally:
                q.put(None)

        loop.run_in_executor(None, _producer)

        while True:
            token = await asyncio.to_thread(q.get)
            if token is None:
                break
            yield token
