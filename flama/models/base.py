import abc
import typing as t

from flama.serialize.data_structures import Metadata

__all__ = ["Model"]


class Model:
    def __init__(self, model: t.Any, meta: "Metadata"):
        self.model = model
        self.meta: "Metadata" = meta

    def inspect(self) -> t.Any:
        return self.meta.to_dict()

    @abc.abstractmethod
    def predict(self, x: t.Any) -> t.Any:
        ...
