import typing as t

from flama import exceptions
from flama.models.base import BaseMLModel

try:
    import transformers
except Exception:  # pragma: no cover
    transformers = None  # ty: ignore[invalid-assignment]

__all__ = ["Model"]


class Model(BaseMLModel):
    """HuggingFace Transformers model wrapper.

    Expects ``self.model`` to be a ready-to-use :class:`transformers.Pipeline`.
    """

    def _prediction(self, x: list[list[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Input features forwarded to the pipeline.
        :return: Pipeline output.
        :raises FrameworkNotInstalled: If transformers is not installed.
        """
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        return self.model(x)
