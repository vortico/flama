import abc
import typing as t

if t.TYPE_CHECKING:
    from flama.serialize.data_structures import Artifacts, Metadata

__all__ = ["Model"]


class Model:
    def __init__(self, model: t.Any, meta: "Metadata", artifacts: t.Optional["Artifacts"]):
        self.model = model
        self.meta = meta
        self.artifacts = artifacts

    def inspect(self) -> t.Any:
        return {"meta": self.meta.to_dict(), "artifacts": self.artifacts}

    @abc.abstractmethod
    def predict(self, x: t.Any) -> t.Any:
        ...
