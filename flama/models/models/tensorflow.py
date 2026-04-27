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

    def _prediction(self, x: list[list[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Input features forwarded to the pipeline.
        :return: Pipeline output.
        :raises FrameworkNotInstalled: If numpy or tensorflow is not installed.
        """
        if np is None:  # noqa
            raise exceptions.FrameworkNotInstalled("numpy")

        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        return self.model.predict(np.array(x)).tolist()
