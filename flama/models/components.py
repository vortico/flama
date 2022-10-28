import abc
import json
import typing

from flama import exceptions
from flama.injection import Component
from flama.serialize import ModelFormat, loads

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore

__all__ = ["Model", "PyTorchModel", "SKLearnModel", "TensorFlowModel", "ModelComponent", "ModelComponentBuilder"]


class Model:
    def __init__(self, model: typing.Any):
        self.model = model

    @abc.abstractmethod
    def inspect(self) -> typing.Any:
        ...

    @abc.abstractmethod
    def predict(self, x: typing.Any) -> typing.Any:
        ...


class PyTorchModel(Model):
    def inspect(self) -> typing.Any:
        return {
            "modules": [str(x) for x in self.model.modules()],
            "parameters": {k: str(v) for k, v in self.model.named_parameters()},
            "state": self.model.state_dict(),
        }

    def predict(self, x: typing.List[typing.List[typing.Any]]) -> typing.Any:
        assert torch is not None, "`torch` must be installed to use PyTorchModel."

        try:
            return self.model(torch.Tensor(x)).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))


class SKLearnModel(Model):
    def inspect(self) -> typing.Any:
        return self.model.get_params()

    def predict(self, x: typing.List[typing.List[typing.Any]]) -> typing.Any:
        try:
            return self.model.predict(x).tolist()
        except ValueError as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))


class TensorFlowModel(Model):
    def inspect(self) -> typing.Any:
        return json.loads(self.model.to_json())

    def predict(self, x: typing.List[typing.List[typing.Any]]) -> typing.Any:
        try:
            return self.model.predict(x).tolist()
        except ValueError:
            raise exceptions.HTTPException(status_code=400)


class ModelComponent(Component):
    def __init__(self, model):
        self.model = model

    def get_model_type(self) -> typing.Type[Model]:
        return self.model.__class__  # type: ignore[no-any-return]


class ModelComponentBuilder:
    MODELS = {
        ModelFormat.pytorch: ("PyTorchModel", PyTorchModel),
        ModelFormat.sklearn: ("SKLearnModel", SKLearnModel),
        ModelFormat.tensorflow: ("TensorFlowModel", TensorFlowModel),
    }

    @classmethod
    def loads(cls, data: bytes) -> ModelComponent:
        load_model = loads(data)
        name, parent = cls.MODELS[load_model.lib]
        model_class = type(name, (parent,), {})
        model_obj = model_class(load_model.model)

        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> model_class:  # type: ignore[valid-type]
                return self.model  # type: ignore[no-any-return]

        return SpecificModelComponent(model_obj)
