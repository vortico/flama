import asyncio
import typing as t

from flama import exceptions
from flama.models.base import BaseModel

try:
    import sklearn
except Exception:  # pragma: no cover
    sklearn = None  # ty: ignore[invalid-assignment]


__all__ = ["Model"]


class Model(BaseModel):
    def predict(self, x: list[list[t.Any]], /) -> t.Any:
        if sklearn is None:  # noqa
            raise exceptions.FrameworkNotInstalled("scikit-learn")

        try:
            return self.model.predict(x).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(self, x: t.Any, /) -> t.AsyncIterator[t.Any]:
        async for item in x:
            try:
                yield await asyncio.to_thread(self.predict, [item])
            except Exception:
                return
