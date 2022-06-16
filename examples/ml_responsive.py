import typing

from sklearn.linear_model import LogisticRegression

from flama import Flama
from flama.models import Model, ModelComponent, ModelResource, ModelResourceType
from flama.resources.routing import resource_method

app = Flama()


# Adding a TensorFlow model:
app.models.add_model(
    "/tf_model",
    "path/to/your_model_file.flm",
    "nn_model",
)


# Adding a Scikit-Learn model:
@app.models.model("/sk_model")
class MySKLearnModel(ModelResource, metaclass=ModelResourceType):
    name = "sk_model"
    verbose_name = "SK-Learn Logistic Regression"
    model_path = "path/to/your_model_file.flm"

    @resource_method("/info", methods=["GET"], name="model-info")
    def info(self):
        return {"name": self.verbose_name}


# Adding a model using a custom component:
model = LogisticRegression()


class CustomModel(Model):
    def inspect(self) -> typing.Any:
        ...

    def predict(self, x: typing.Any) -> typing.Any:
        ...


class CustomModelComponent(ModelComponent):
    def resolve(self) -> CustomModel:
        return self.model


component = CustomModelComponent(model)


class CustomModelResource(ModelResource, metaclass=ModelResourceType):
    name = "custom"
    verbose_name = "Custom"
    component = component


app.add_component(component)
app.models.add_model_resource("/", CustomModelResource)
