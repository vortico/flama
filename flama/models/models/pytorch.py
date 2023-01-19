import typing as t

from flama import exceptions
from flama.models.base import Model

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore


class PyTorchModel(Model):
    def predict(self, x: t.List[t.List[t.Any]]) -> t.Any:
        assert torch is not None, "`torch` must be installed to use PyTorchModel."

        try:
            return self.model(torch.Tensor(x)).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))
