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

__all__ = ["Model"]


class Model(BaseLLMModel):
    """vLLM large-language-model wrapper.

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
