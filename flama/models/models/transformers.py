import threading
import typing as t

from flama import exceptions
from flama.models.base import BaseModel

try:
    import transformers
except Exception:  # pragma: no cover
    transformers = None  # ty: ignore[invalid-assignment]

__all__ = ["Model"]


def _should_stop(stop_event: threading.Event | None) -> bool:
    return stop_event is not None and stop_event.is_set()


def _build_stopping_criteria(stop_event: threading.Event | None):
    if stop_event is None:
        return None

    class StopOnEvent(transformers.StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs):
            return stop_event.is_set()

    return transformers.StoppingCriteriaList([StopOnEvent()])


def _build_generation_kwargs(
    inputs: dict[str, t.Any], streamer: t.Any, stopping_criteria: t.Any, **generation_kwargs: t.Any
) -> dict[str, t.Any]:
    kwargs = {**inputs, **generation_kwargs, "streamer": streamer}
    if stopping_criteria is not None:
        kwargs["stopping_criteria"] = stopping_criteria

    return kwargs


class Model(BaseModel):
    DEFAULT_GENERATION_KWARGS: t.ClassVar[dict[str, t.Any]] = {
        "max_new_tokens": 2048,
        "do_sample": True,
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 50,
        "repetition_penalty": 1.1,
    }

    def __init__(self, model: t.Any, meta: t.Any, artifacts: t.Any) -> None:
        super().__init__(model, meta, artifacts)
        self.generation_kwargs: dict[str, t.Any] = dict(self.DEFAULT_GENERATION_KWARGS)
        self.enable_thinking: bool = False
        self.system_prompt: str | None = None

    def _has_chat_template(self) -> bool:
        tokenizer = self.model.tokenizer
        return hasattr(tokenizer, "chat_template") and tokenizer.chat_template is not None

    def _prepare_chat_inputs(self, x: list[list[t.Any]]) -> dict[str, t.Any]:
        tokenizer = self.model.tokenizer
        user_text = x[0][0] if isinstance(x[0], list) else x[0]

        messages: list[dict[str, t.Any]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_text})

        kwargs: dict[str, t.Any] = {
            "add_generation_prompt": True,
            "tokenize": True,
            "return_dict": True,
            "return_tensors": "pt",
        }
        if self.enable_thinking:
            kwargs["enable_thinking"] = True

        return tokenizer.apply_chat_template(messages, **kwargs)

    def _tokenize(self, x: list[list[t.Any]]) -> dict[str, t.Any]:
        if self._has_chat_template():
            return self._prepare_chat_inputs(x)
        return self.model.tokenizer(x, return_tensors="pt", padding=True, truncation=True)

    def predict(self, x: list[list[t.Any]]) -> t.Any:
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        try:
            tokenizer = self.model.tokenizer
            model = self.model.model
            model.eval()
            inputs = self._tokenize(x)
            input_length = inputs["input_ids"].shape[1]
            outputs = model.generate(**inputs, **self.generation_kwargs)
            return tokenizer.batch_decode(outputs[:, input_length:], skip_special_tokens=True)
        except Exception as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    def predict_stream(self, x: list[list[t.Any]], stop_event: threading.Event | None = None) -> t.Iterator[str]:
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        try:
            tokenizer = self.model.tokenizer
            model = self.model.model
            model.eval()
            inputs = self._tokenize(x)

            streamer = transformers.TextIteratorStreamer(tokenizer, skip_special_tokens=True, skip_prompt=True)
            stopping_criteria = _build_stopping_criteria(stop_event)

            generation_error: list[BaseException] = []

            def _generate():
                try:
                    model.generate(
                        **_build_generation_kwargs(inputs, streamer, stopping_criteria, **self.generation_kwargs)
                    )
                except BaseException as exc:
                    generation_error.append(exc)
                    streamer.text_queue.put(streamer.stop_signal)

            thread = threading.Thread(target=_generate)
            thread.start()

            for token in streamer:
                if _should_stop(stop_event):
                    break
                yield token

            thread.join()

            if generation_error:
                raise generation_error[0]
        except Exception as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))
