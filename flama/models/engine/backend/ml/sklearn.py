import typing as t

from flama import _imports
from flama.models.engine.backend.ml._base import MLBackend

__all__ = ["SklearnBackend"]

sklearn = _imports.Dependency("sklearn")


class SklearnBackend(MLBackend):
    """Scikit-learn backend.

    Expects ``self.model`` to be a ready-to-use scikit-learn estimator exposing ``predict``.
    """

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the estimator on the given input features.

        :param x: Batch of input feature vectors forwarded to the estimator.
        :return: Predictions as a plain Python list.
        :raises DependencyNotInstalled: If scikit-learn is not installed.
        """
        sklearn.require()

        return self.model.predict(x).tolist()
