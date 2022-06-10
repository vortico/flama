from flama import Flama
from flama.models import ModelResource, ModelResourceType
from flama.resources.routing import resource_method

app = Flama()


# Adding a TensorFlow model:
app.models.add_model(
    "/tf_model",
    "path/to/your_model_file.flm",
    "nn_model",
)


# Adding a Scikit-Learn model:
@app.resources.resource("/sk_model")
class MySKLearnModel(ModelResource, metaclass=ModelResourceType):
    name = "sk_model"
    verbose_name = "SK-Learn Logistic Regression"
    model = "path/to/your_model_file.flm"

    @resource_method("/info", methods=["GET"], name="model-info")
    def info(self):
        return {"name": self.verbose_name}
