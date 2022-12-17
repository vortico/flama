import typing
from datetime import datetime

import flama
from flama import Flama
from flama.models import Model, ModelResource, ModelResourceType, ModelComponent
from flama.resources import resource_method


class MySKModel(Model):
    def inspect(self) -> typing.Any:
        return self.model.get_params()

    def predict(self, x: typing.Any) -> typing.Any:
        return self.model.predict(x)


class MySKModelComponent(ModelComponent):

    def __init__(self, model_path: str):
        self._model_path = model_path
        self.model = MySKModel(None)

    def load_model(self):
        with open(self._model_path, "rb") as f:
            self.model = MySKModel(flama.load(f).model)

    def unload_model(self):
        self.model = MySKModel(None)

    def resolve(self) -> MySKModel:
        if not self.model.model:
            self.load_model()

        return self.model


component = MySKModelComponent("sklearn_model.flm")


class MySKModelResource(ModelResource, metaclass=ModelResourceType):
    name = "custom_model"
    verbose_name = "Lazy-loaded ScikitLearn Model"
    component = component

    info = {
        "model_version": "1.0.0",
        "library_version": "1.0.2",
    }

    def _get_metadata(self):
        return {
            "metadata": {
                "built-in": {
                    "verbose_name": self._meta.verbose_name,
                    "name": self._meta.name,
                },
                "custom": {
                    **self.info,
                    "loaded": self.component.model.model is not None,
                    "date": datetime.now().date(),
                    "time": datetime.now().time()
                },
            }
        }

    @resource_method("/unload/", methods=["GET"], name="unload-method")
    def unload(self):
        """
        tags:
            - Lazy-loaded ScikitLearn Model
        summary:
            Unload the model.
        """
        self.component.unload_model()
        return self._get_metadata()

    @resource_method("/metadata/", methods=["GET"], name="metadata-method")
    def metadata(self):
        """
        tags:
            - Lazy-loaded ScikitLearn Model
        summary:
            Get metadata info.
        """
        return self._get_metadata()


app = Flama(
    title="Flama ML",
    version="0.1.0",
    description="Machine learning API using Flama 🔥",
    docs="/docs/",
    components=[component],
)

app.models.add_model_resource(path="/model", resource=MySKModelResource)


if __name__ == "__main__":
    flama.run(flama_app="__main__:app", server_host="0.0.0.0", server_port=8080, server_reload=True)
