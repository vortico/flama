import typing as t

from flama import exceptions
from flama.models.engine.backend.ml._base import MLBackend

try:
    import transformers
except Exception:  # pragma: no cover
    transformers = None

__all__ = ["TransformersBackend"]


class TransformersBackend(MLBackend):
    """HuggingFace Transformers pipeline backend.

    Expects ``self.model`` to be a ready-to-use :class:`transformers.Pipeline`.
    """

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Batch of input feature vectors forwarded to the pipeline.
        :return: Pipeline output.
        :raises FrameworkNotInstalled: If transformers is not installed.
        """
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        return self.model(x)
