import typing

from sklearn.linear_model import LogisticRegression

import flama
from flama import Flama
from flama.models import ModelComponent, ModelResource, ModelResourceType
from flama.models.base import Model
from flama.resources.routing import ResourceRoute

app = Flama()


# Adding a TensorFlow model:
app.models.add_model(
    "/model",
    "path/to/your_model_file.flm",
    "model",
)


# Adding a model using a ModelResource:
@app.models.model_resource("/model_resource")
class SKLearnModelResource(ModelResource, metaclass=ModelResourceType):
    name = "sklearn_model"
    verbose_name = "SK-Learn Logistic Regression"
    model_path = "path/to/your_model_file.flm"

    @ResourceRoute.method("/info", methods=["GET"], name="model-info")
    def info(self):
        return {"name": self.verbose_name}


# Adding a model using a custom component:
model = LogisticRegression()


class CustomModel(Model):
    def inspect(self) -> typing.Any:
        return self.model.__dict__

    def predict(self, x: typing.Any) -> typing.Any:
        return self.model.predict(x)


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

if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
