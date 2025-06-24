import typing as t
from datetime import datetime

import pydantic

import flama
from flama import Flama, schemas
from flama.models import ModelResource
from flama.resources import ResourceRoute

app = Flama(
    openapi={
        "info": {
            "title": "Flama ML",
            "version": "0.1.0",
            "description": "Machine learning API using Flama 🔥",
        }
    },
    docs="/docs/",
)


class X(pydantic.BaseModel):
    input: list[t.Any] = pydantic.Field(title="input", description="Model input")


class Y(pydantic.BaseModel):
    output: list[t.Any] = pydantic.Field(title="output", description="Model output")


app.schema.register_schema("X", X)
app.schema.register_schema("Y", Y)


class MySKModel(ModelResource):
    # special names:
    name = "sk_model"
    verbose_name = "My ScikitLearn Model"
    model_path = "sklearn_model.flm"

    # custom attributes
    info = {
        "model_version": "1.0.0",
        "library_version": "1.0.2",
    }

    @ResourceRoute.method("/predict/", methods=["POST"], name="model-predict")
    def predict(
        self, data: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(X)]
    ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(Y)]:
        """
        tags:
            - My ScikitLearn Model
        summary:
            Run predict method.
        description:
            Runs a prediction using the model from this resource.
        responses:
            200:
                description: ML model prediction.
        """
        return {"output": self.model.predict(data["input"])}

    @ResourceRoute.method("/inspect/", methods=["GET"], name="model-inspect-model")
    def inspect_model(self):
        """
        tags:
            - My ScikitLearn Model
        summary:
            Run model inspect method.
        description:
            Run the built-in inspect method of the model.
        responses:
            200:
                description: Model inspection.
        """
        return {"params": self.model.inspect()}

    @ResourceRoute.method("/metadata/", methods=["GET"], name="metadata-method")
    def metadata(self):
        """
        tags:
            - My ScikitLearn Model
        summary:
            Get metadata info.
        description:
            Return metadata info about the model, showing both the bui
        responses:
            200:
                description: ML model metadata.
        """
        return {
            "metadata": {
                "built-in": {
                    "verbose_name": self._meta.verbose_name,
                    "name": self._meta.name,
                },
                "custom": {
                    **self.info,
                    "date": datetime.now().date(),
                    "time": datetime.now().time(),
                },
            }
        }


app.models.add_model_resource(path="/model", resource=MySKModel)

if __name__ == "__main__":
    flama.run(flama_app="__main__:app", server_host="0.0.0.0", server_port=8080, server_reload=True)
