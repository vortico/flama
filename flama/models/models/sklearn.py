import asyncio
import typing as t

from flama import exceptions
from flama.models.base import BaseMLModel

try:
    import sklearn
except Exception:  # pragma: no cover
    sklearn = None  # ty: ignore[invalid-assignment]


__all__ = ["Model"]


class Model(BaseMLModel):
    """Scikit-learn model wrapper.

    Expects ``self.model`` to be a ready-to-use scikit-learn model.
    """

    def predict(self, x: list[list[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Input features forwarded to the pipeline.
        :return: Pipeline output.
        :raises HTTPException: If the pipeline raises an error.
        """
        if sklearn is None:  # noqa
            raise exceptions.FrameworkNotInstalled("scikit-learn")

        try:
            return self.model.predict(x).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(self, x: t.Any, /) -> t.AsyncIterator[t.Any]:
        """Yield pipeline results for each item in an async input stream.

        :param x: Async-iterable input.
        :return: Async iterator of pipeline outputs.
        """
        async for item in x:
            try:
                yield await asyncio.to_thread(self.predict, [item])
            except Exception:
                return
