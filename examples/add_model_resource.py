import typesystem as ts

from datetime import datetime

import flama
from flama import Flama
from flama.models import ModelResource, ModelResourceType
from flama.resources import resource_method
from flama.exceptions import HTTPException

app = Flama(
    title="Flama ML",
    version="0.1.0",
    description="Machine learning API using Flama 🔥",
    docs="/docs/"
)


X = ts.Schema(fields={"input": ts.fields.Array()})
Y = ts.Schema(fields={"output": ts.fields.Array()})

app.schema.register_schema("X", X)
app.schema.register_schema("Y", Y)


class MySKModel(ModelResource, metaclass=ModelResourceType):
    # special names:
    name = "sk_model"
    verbose_name = "My ScikitLearn Model"
    model_path = "sklearn_model.flm"

    @resource_method("/predict", methods=["POST"], name="model-predict")
    def predict(self, data: X) -> Y:
        """
        tags:
            - My ScikitLearn Model
        summary:
            Run predict method.
        description:
            This is a more detailed description of the method itself.
            Here we can give all the details required and they will appear
            automatically in the auto-generated docs.
        responses:
            200:
                description: ML model prediction.
        """
        try:
            return {"output": self.model.predict(data["input"])}
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    # custom attributes
    info = {
        "model_version": "1.0.0",
        "library_version": "1.0.2",
    }

    @resource_method("/metadata", methods=["GET"], name="metadata-method")
    def metadata(self):
        """
        tags:
            - My ScikitLearn Model
        summary:
            Get metadata info.
        description:
            This is a more detailed description of the method itself.
            Here we can give all the details required and they will appear
            automatically in the auto-generated docs.
        responses:
            200:
                description: Verbose name of the ML model.
        """

        return {
            "metadata": {"built-in": self._meta.verbose_name},
            "custom": {**self.info, "date": datetime.now().date(), "time": datetime.now().time()},
        }


app.models.add_model_resource(path="/model", resource=MySKModel)

if __name__ == "__main__":
    flama.run(flama_app="__main__:app", server_host="0.0.0.0", server_port=8080, server_reload=True)
