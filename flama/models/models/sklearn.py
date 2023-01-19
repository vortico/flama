import typing as t

from flama import exceptions
from flama.models.base import Model


class SKLearnModel(Model):
    def predict(self, x: t.List[t.List[t.Any]]) -> t.Any:
        try:
            return self.model.predict(x).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))
