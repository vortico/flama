import typing as t

from flama import _imports
from flama.models.engine.backend.ml._base import MLBackend

__all__ = ["TransformersBackend"]

transformers = _imports.Dependency("transformers")


class TransformersBackend(MLBackend):
    """HuggingFace Transformers pipeline backend.

    Expects ``self.model`` to be a ready-to-use :class:`transformers.Pipeline`.
    """

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Batch of input feature vectors forwarded to the pipeline.
        :return: Pipeline output.
        :raises DependencyNotInstalled: If transformers is not installed.
        """
        transformers.require()

        return self.model(x)
