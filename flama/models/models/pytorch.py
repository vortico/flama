import asyncio
import typing as t

from flama import exceptions
from flama.models.base import BaseMLModel

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # ty: ignore[invalid-assignment]

__all__ = ["Model"]


class Model(BaseMLModel):
    """PyTorch model wrapper.

    Expects ``self.model`` to be a ready-to-use pytorch model.
    """

    def predict(self, x: list[list[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Input features forwarded to the pipeline.
        :return: Pipeline output.
        :raises HTTPException: If the pipeline raises an error.
        """
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        try:
            return self.model(torch.Tensor(x)).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(self, x: t.Any, /) -> t.AsyncIterator[t.Any]:
        """Yield pipeline results for each item in an async input stream.

        :param x: Async-iterable input.
        :return: Async iterator of pipeline outputs.
        """
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        async for item in x:
            try:
                yield await asyncio.to_thread(lambda i=item: self.model(torch.Tensor([i])).tolist())
            except Exception:
                return
