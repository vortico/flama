import typing

import torch

from flama import Flama
from flama.models import Model, ModelComponent, ModelResource, ModelResourceType
from flama.resources.routing import resource_method

app = Flama()


# Adding a model:
app.models.add_model(
    "/model",
    "path/to/your_model_file.flm",
    "model",
)


# Adding a model using a ModelResource:
@app.models.model("/model_resource")
class PyTorchModelResource(ModelResource, metaclass=ModelResourceType):
    name = "pytorch_model"
    verbose_name = "PyTorch Logistic Regression"
    model_path = "path/to/your_model_file.flm"

    @resource_method("/info", methods=["GET"], name="model-info")
    def info(self):
        return {"name": self.verbose_name}


# Adding a model using a custom component:
class PyTorchModel(torch.nn.Module):
    def forward(self, x):
        return x + 10


model = PyTorchModel()


class CustomModel(Model):
    def inspect(self) -> typing.Any:
        return self.model.__dict__

    def predict(self, x: typing.Any) -> typing.Any:
        return self.model(x)


class CustomModelComponent(ModelComponent):
    def resolve(self) -> CustomModel:
        return self.model


component = CustomModelComponent(model)


class CustomModelResource(ModelResource, metaclass=ModelResourceType):
    name = "custom_model"
    verbose_name = "Custom model"
    component = component


app.add_component(component)
app.models.add_model_resource("/", CustomModelResource)
