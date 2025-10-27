import typing as t

from flama import exceptions
from flama.models.base import BaseModel

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore

__all__ = ["Model"]


class Model(BaseModel):
    def predict(self, x: list[list[t.Any]]) -> t.Any:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        try:
            return self.model(torch.Tensor(x)).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))
