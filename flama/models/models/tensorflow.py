import typing as t

from flama import exceptions
from flama.models.base import Model

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None

try:
    import tensorflow as tf  # type: ignore
except Exception:  # pragma: no cover
    tf = None


class TensorFlowModel(Model):
    def predict(self, x: list[list[t.Any]]) -> t.Any:
        if np is None:  # noqa
            raise exceptions.FrameworkNotInstalled("numpy")

        if tf is None:  # noqa
            raise exceptions.FrameworkNotInstalled("tensorflow")

        try:
            return self.model.predict(np.array(x)).tolist()
        except (tf.errors.OpError, ValueError):  # type: ignore
            raise exceptions.HTTPException(status_code=400)
