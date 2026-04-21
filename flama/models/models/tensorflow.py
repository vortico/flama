import asyncio
import typing as t

from flama import exceptions
from flama.models.base import BaseMLModel

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # ty: ignore[invalid-assignment]

try:
    import tensorflow as tf
except Exception:  # pragma: no cover
    tf = None  # ty: ignore[invalid-assignment]


__all__ = ["Model"]


class Model(BaseMLModel):
    """Tensorflow model wrapper.

    Expects ``self.model`` to be a ready-to-use tensorflow model.
    """

    def predict(self, x: list[list[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Input features forwarded to the pipeline.
        :return: Pipeline output.
        :raises HTTPException: If the pipeline raises an error.
        """
        if np is None:  # noqa
            raise exceptions.FrameworkNotInstalled("numpy")

        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        try:
            return self.model.predict(np.array(x)).tolist()
        except (tf.errors.OpError, ValueError):
            raise exceptions.HTTPException(status_code=400)

    async def stream(self, x: t.Any, /) -> t.AsyncIterator[t.Any]:
        """Yield pipeline results for each item in an async input stream.

        :param x: Async-iterable input.
        :return: Async iterator of pipeline outputs.
        """
        if np is None:  # noqa
            raise exceptions.FrameworkNotInstalled("numpy")

        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        async for item in x:
            try:
                yield await asyncio.to_thread(lambda i=item: self.model.predict(np.array([i])).tolist())
            except Exception:
                return
