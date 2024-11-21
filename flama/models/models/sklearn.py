import typing as t

from flama import exceptions
from flama.models.base import Model

try:
    import sklearn  # type: ignore
except Exception:  # pragma: no cover
    sklearn = None


class SKLearnModel(Model):
    def predict(self, x: list[list[t.Any]]) -> t.Any:
        if sklearn is None:  # noqa
            raise exceptions.FrameworkNotInstalled("scikit-learn")

        try:
            return self.model.predict(x).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))
