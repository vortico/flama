import typing as t

from flama import exceptions
from flama.models.base import BaseMLModel

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # ty: ignore[invalid-assignment]

__all__ = ["Model"]


class Model(BaseMLModel):
    """PyTorch model wrapper.

    Expects ``self.model`` to be a ready-to-use pytorch model.
    """

    def _prediction(self, x: list[list[t.Any]], /) -> t.Any:
        """Run the pipeline on the given input features.

        :param x: Input features forwarded to the pipeline.
        :return: Pipeline output.
        :raises FrameworkNotInstalled: If pytorch is not installed.
        """
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        return self.model(torch.Tensor(x)).tolist()
