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

    def _prediction(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Batch of input feature vectors forwarded to the pipeline.
        :return: Pipeline output.
        :raises FrameworkNotInstalled: If scikit-learn is not installed.
        """
        if sklearn is None:  # noqa
            raise exceptions.FrameworkNotInstalled("scikit-learn")

        return self.model.predict(x).tolist()
