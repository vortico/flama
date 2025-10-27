import typing as t

from flama import exceptions
from flama.models.base import BaseModel

try:
    import sklearn  # type: ignore
except Exception:  # pragma: no cover
    sklearn = None


__all__ = ["Model"]


class Model(BaseModel):
    def predict(self, x: list[list[t.Any]]) -> t.Any:
        if sklearn is None:  # noqa
            raise exceptions.FrameworkNotInstalled("scikit-learn")

        try:
            return self.model.predict(x).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))
