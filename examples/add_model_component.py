import typing
from datetime import datetime

import flama
from flama import Flama
from flama.models import BaseModelResource, ModelComponent
from flama.models.base import Model
from flama.resources import ResourceRoute


class MyCustomModel(Model):
    def inspect(self) -> typing.Any:
        return self.model.get_params()

    def predict(self, x: typing.Any) -> typing.Any:
        return self.model.predict(x)


class MyCustomModelComponent(ModelComponent):
    def __init__(self, model_path: str):
        self._model_path = model_path
        self.model = None

    def load(self):
        load_model = flama.load(self._model_path)
        self.model = MyCustomModel(load_model.model, load_model.meta, load_model.artifacts)

    def reset(self):
        self.model = None

    def resolve(self) -> MyCustomModel:
        if not self.model:
            self.load()

        assert self.model
        return self.model


component = MyCustomModelComponent("sklearn_model.flm")
# component = MyCustomModelComponent("pytorch_model.flm")
# component = MyCustomModelComponent("tensorflow_model.flm")


class MyCustomModelResource(BaseModelResource[MyCustomModelComponent]):
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
                    "loaded": self.component.model is not None,
                    "date": datetime.now().date(),
                    "time": datetime.now().time(),
                },
            }
        }

    @ResourceRoute.method("/unload/", methods=["GET"], name="unload-method")
    def unload(self):
        """
        tags:
            - Lazy-loaded ScikitLearn Model
        summary:
            Unload the model.
        """
        self.component.reset()
        return self._get_metadata()

    @ResourceRoute.method("/metadata/", methods=["GET"], name="metadata-method")
    def metadata(self):
        """
        tags:
            - Lazy-loaded ScikitLearn Model
        summary:
            Get metadata info.
        """
        return self._get_metadata()


app = Flama(
    openapi={
        "info": {
            "title": "Flama ML",
            "version": "0.1.0",
            "description": "Machine learning API using Flama 🔥",
        }
    },
    docs="/docs/",
    components=[component],
)

app.models.add_model_resource(path="/model", resource=MyCustomModelComponent)

if __name__ == "__main__":
    flama.run(flama_app="__main__:app", server_host="0.0.0.0", server_port=8080, server_reload=True)
