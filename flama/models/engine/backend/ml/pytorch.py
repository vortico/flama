import typing as t

from flama import _imports
from flama.models.engine.backend.ml._base import MLBackend

__all__ = ["PytorchBackend"]

torch = _imports.Dependency("torch")


class PytorchBackend(MLBackend):
    """PyTorch backend.

    Expects ``self.model`` to be a ready-to-use callable PyTorch module.
    """

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the model on the given input features.

        :param x: Batch of input feature vectors forwarded as a tensor.
        :return: Predictions as a plain Python list.
        :raises DependencyNotInstalled: If pytorch is not installed.
        """
        torch.require()

        return self.model(torch.Tensor(x)).tolist()
