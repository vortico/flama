import abc
import typing as t

from flama import exceptions
from flama.injection import Component
from flama.serialize import loads
from flama.serialize.types import Framework

if t.TYPE_CHECKING:
    from flama.serialize.data_structures import Metadata

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore

try:
    import tensorflow
except Exception:  # pragma: no cover
    tensorflow = None  # type: ignore

__all__ = ["Model", "PyTorchModel", "SKLearnModel", "TensorFlowModel", "ModelComponent", "ModelComponentBuilder"]


class Model:
    def __init__(self, model: t.Any, meta: "Metadata"):
        self.model = model
        self.meta: "Metadata" = meta

    def inspect(self) -> t.Any:
        return self.meta.to_dict()

    @abc.abstractmethod
    def predict(self, x: t.Any) -> t.Any:
        ...


class PyTorchModel(Model):
    def predict(self, x: t.List[t.List[t.Any]]) -> t.Any:
        assert torch is not None, "`torch` must be installed to use PyTorchModel."

        try:
            return self.model(torch.Tensor(x)).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))


class SKLearnModel(Model):
    def predict(self, x: t.List[t.List[t.Any]]) -> t.Any:
        try:
            return self.model.predict(x).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))


class TensorFlowModel(Model):
    def predict(self, x: t.List[t.List[t.Any]]) -> t.Any:
        assert tensorflow is not None, "`tensorflow` must be installed to use TensorFlowModel."

        try:
            return self.model.predict(x).tolist()
        except (tensorflow.errors.OpError, ValueError):
            raise exceptions.HTTPException(status_code=400)


class ModelComponent(Component):
    def __init__(self, model):
        self.model = model

    def get_model_type(self) -> t.Type[Model]:
        return self.model.__class__  # type: ignore[no-any-return]


class ModelComponentBuilder:
    MODELS = {
        Framework.torch: ("PyTorchModel", PyTorchModel),
        Framework.sklearn: ("SKLearnModel", SKLearnModel),
        Framework.tensorflow: ("TensorFlowModel", TensorFlowModel),
    }

    @classmethod
    def loads(cls, data: bytes) -> ModelComponent:
        load_model = loads(data)
        name, parent = cls.MODELS[load_model.meta.framework.lib]
        model_class = type(name, (parent,), {})
        model_obj = model_class(load_model.model, load_model.meta)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:  # type: ignore[valid-type]
                return self.model  # type: ignore[no-any-return]

        return SpecificModelComponent(model_obj)
