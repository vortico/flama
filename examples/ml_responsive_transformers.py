import flama
from flama import Flama
from flama.models import ModelResource, ModelResourceType
from flama.resources.routing import ResourceRoute

app = Flama()


# Adding a transformers model directly from a HuggingFace identifier:
app.models.add_model(
    "/models/tiny-gpt2",
    "sshleifer/tiny-gpt2",
    "tiny-gpt2",
)


@app.models.model_resource("/tiny-gpt2")
class TinyGPT2Resource(ModelResource, metaclass=ModelResourceType):
    name = "tiny_gpt2"
    verbose_name = "Tiny GPT-2"
    model_path = "sshleifer/tiny-gpt2"
    generation_kwargs = {"max_new_tokens": 128, "temperature": 0.9, "top_p": 0.9, "do_sample": True}

    @ResourceRoute.method("/info", methods=["GET"], name="model-info")
    def info(self):
        return {"name": self._meta.verbose_name}


@app.models.model_resource("/gemma4-e4b")
class Gemma426BE4BResource(ModelResource, metaclass=ModelResourceType):
    name = "gemma4_26b_e4b"
    verbose_name = "Gemma4 26B E4B"
    model_path = "google/gemma-4-E4B"
    enable_thinking = True
    generation_kwargs = {
        "max_new_tokens": 512,
        "do_sample": True,
        "temperature": 0.5,
        "top_p": 0.95,
        "top_k": 50,
        "repetition_penalty": 1.1,
    }

    @ResourceRoute.method("/info", methods=["GET"], name="model-info")
    def info(self):
        return {"name": self._meta.verbose_name}


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
