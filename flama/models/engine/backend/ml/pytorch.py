import typing as t

from flama import exceptions
from flama.models.engine.backend.ml.base import MLBackend

try:
    import torch
except Exception:  # pragma: no cover
    torch = None

__all__ = ["PytorchBackend"]


class PytorchBackend(MLBackend):
    """PyTorch backend.

    Expects ``self.model`` to be a ready-to-use callable PyTorch module.
    """

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the model on the given input features.

        :param x: Batch of input feature vectors forwarded as a tensor.
        :return: Predictions as a plain Python list.
        :raises FrameworkNotInstalled: If pytorch is not installed.
        """
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        return self.model(torch.Tensor(x)).tolist()
