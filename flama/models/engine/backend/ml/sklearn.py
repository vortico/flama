import typing as t

from flama import exceptions
from flama.models.engine.backend.ml._base import MLBackend

try:
    import sklearn
except Exception:  # pragma: no cover
    sklearn = None

__all__ = ["SklearnBackend"]


class SklearnBackend(MLBackend):
    """Scikit-learn backend.

    Expects ``self.model`` to be a ready-to-use scikit-learn estimator exposing ``predict``.
    """

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the estimator on the given input features.

        :param x: Batch of input feature vectors forwarded to the estimator.
        :return: Predictions as a plain Python list.
        :raises FrameworkNotInstalled: If scikit-learn is not installed.
        """
        if sklearn is None:  # noqa
            raise exceptions.FrameworkNotInstalled("scikit-learn")

        return self.model.predict(x).tolist()
