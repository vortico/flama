import typing as t

from flama import exceptions
from flama.models.engine.backend.ml._base import MLBackend

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import tensorflow as tf
except Exception:  # pragma: no cover
    tf = None


__all__ = ["TensorflowBackend"]


class TensorflowBackend(MLBackend):
    """TensorFlow / Keras backend.

    Expects ``self.model`` to be a ready-to-use TensorFlow/Keras model exposing ``predict``.
    """

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the model on the given input features.

        :param x: Batch of input feature vectors forwarded as a numpy array.
        :return: Predictions as a plain Python list.
        :raises FrameworkNotInstalled: If numpy or tensorflow is not installed.
        """
        if np is None:  # noqa
            raise exceptions.FrameworkNotInstalled("numpy")

        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        return self.model.predict(np.array(x)).tolist()
