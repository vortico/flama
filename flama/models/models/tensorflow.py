import typing as t

from flama import exceptions
from flama.models.base import Model

try:
    import tensorflow as tf  # type: ignore
except Exception:  # pragma: no cover
    tf = None


class TensorFlowModel(Model):
    def predict(self, x: t.List[t.List[t.Any]]) -> t.Any:
        assert tf is not None, "`tensorflow` must be installed to use TensorFlowModel."

        try:
            return self.model.predict(x).tolist()
        except (tf.errors.OpError, ValueError):  # type: ignore
            raise exceptions.HTTPException(status_code=400)
