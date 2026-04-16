import asyncio
import typing as t

from flama import exceptions
from flama.models.base import BaseModel

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # ty: ignore[invalid-assignment]

__all__ = ["Model"]


class Model(BaseModel):
    def predict(self, x: list[list[t.Any]], /) -> t.Any:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        try:
            return self.model(torch.Tensor(x)).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(self, x: t.Any, /) -> t.AsyncIterator[t.Any]:
        if torch is None:  # noqa
            raise exceptions.FrameworkNotInstalled("pytorch")

        async for item in x:
            try:
                yield await asyncio.to_thread(lambda i=item: self.model(torch.Tensor([i])).tolist())
            except Exception:
                return
