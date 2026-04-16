import asyncio
import pathlib
import threading
import typing as t

from flama import exceptions
from flama.models.base import BaseModel

try:
    import transformers as tf_hub
except Exception:  # pragma: no cover
    tf_hub = None  # ty: ignore[invalid-assignment]

if t.TYPE_CHECKING:
    from flama.serialize.data_structures import Artifacts, Metadata

__all__ = ["Model"]


class Model(BaseModel):
    def __init__(self, model: t.Any, meta: "Metadata", artifacts: "Artifacts | None"):
        super().__init__(model, meta, artifacts)

        if tf_hub is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        descriptor = model if isinstance(model, dict) else {}
        task = descriptor.get("task")

        artifacts_dir = self._resolve_artifacts_dir(artifacts)
        self.pipeline: t.Any = tf_hub.pipeline(task=task, model=str(artifacts_dir))

    @staticmethod
    def _resolve_artifacts_dir(artifacts: "Artifacts | None") -> pathlib.Path:
        if not artifacts:
            raise ValueError("Transformers model requires artifacts containing the model files.")

        paths = [pathlib.Path(str(p)) for p in artifacts.values()]
        parents = {p.parent for p in paths}
        if len(parents) == 1:
            return parents.pop()

        # Find the common ancestor
        return pathlib.Path(*[p for p in pathlib.Path.cwd().parts if all(str(a).startswith(str(p)) for a in parents)])

    def predict(self, x: list[list[t.Any]], /) -> t.Any:
        if tf_hub is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        try:
            return self.pipeline(x)
        except Exception as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(self, x: t.Any, /) -> t.AsyncIterator[t.Any]:
        if tf_hub is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        has_generate = hasattr(self.pipeline.model, "generate") and hasattr(tf_hub, "TextIteratorStreamer")

        async for item in x:
            if has_generate:
                try:
                    for token in await asyncio.to_thread(self._generate_tokens, item):
                        yield token
                except Exception:
                    return
            else:
                try:
                    yield await asyncio.to_thread(self.pipeline, item)
                except Exception:
                    return

    def _generate_tokens(self, item: t.Any) -> list[str]:
        streamer = tf_hub.TextIteratorStreamer(self.pipeline.tokenizer, skip_prompt=True, skip_special_tokens=True)

        inputs = self.pipeline.tokenizer(item, return_tensors="pt")
        if hasattr(self.pipeline.model, "device"):
            inputs = {k: v.to(self.pipeline.model.device) for k, v in inputs.items()}

        thread = threading.Thread(
            target=self.pipeline.model.generate,
            kwargs={**inputs, "streamer": streamer, "max_new_tokens": 256},
        )
        thread.start()

        tokens = []
        try:
            for token in streamer:
                if token:
                    tokens.append(token)
        finally:
            thread.join()

        return tokens
