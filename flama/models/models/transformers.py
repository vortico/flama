import asyncio
import typing as t

from flama import exceptions
from flama.models.base import BaseMLModel

__all__ = ["Model"]


class Model(BaseMLModel):
    """HuggingFace Transformers model wrapper.

    Expects ``self.model`` to be a ready-to-use :class:`transformers.Pipeline`.
    """

    def predict(self, x: list[list[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Input features forwarded to the pipeline.
        :return: Pipeline output.
        :raises HTTPException: If the pipeline raises an error.
        """
        try:
            return self.model(x)
        except Exception as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(self, x: t.Any, /) -> t.AsyncIterator[t.Any]:
        """Yield pipeline results for each item in an async input stream.

        :param x: Async-iterable input.
        :return: Async iterator of pipeline outputs.
        """
        async for item in x:
            try:
                yield await asyncio.to_thread(self.model, item)
            except Exception:
                return
