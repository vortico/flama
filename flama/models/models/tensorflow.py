import typing as t

from flama import exceptions
from flama.models.base import Model

try:
    import tensorflow
except Exception:  # pragma: no cover
    tensorflow = None  # type: ignore


class TensorFlowModel(Model):
    def predict(self, x: t.List[t.List[t.Any]]) -> t.Any:
        assert tensorflow is not None, "`tensorflow` must be installed to use TensorFlowModel."

        try:
            return self.model.predict(x).tolist()
        except (tensorflow.errors.OpError, ValueError):
            raise exceptions.HTTPException(status_code=400)
