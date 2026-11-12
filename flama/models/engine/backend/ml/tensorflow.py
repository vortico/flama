import typing as t

from flama import _imports
from flama.models.engine.backend.ml._base import MLBackend

__all__ = ["TensorflowBackend"]

tf = _imports.Dependency("tensorflow")


class TensorflowBackend(MLBackend):
    """TensorFlow / Keras backend.

    Expects ``self.model`` to be a ready-to-use TensorFlow/Keras model exposing ``predict``.
    """

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the model on the given input features.

        :param x: Batch of input feature vectors forwarded as a tensor.
        :return: Predictions as a plain Python list.
        :raises DependencyNotInstalled: If tensorflow is not installed.
        """
        tf.require()

        return self.model.predict(tf.convert_to_tensor(x)).tolist()
