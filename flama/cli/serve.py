import click
import uvicorn

from flama import Flama


@click.command()
@click.argument("flama-model", envvar="FLAMA_MODEL")
@click.argument("flama-model-url", envvar="FLAMA_MODEL_URL", default="/")
@click.argument("flama-model-name", envvar="FLAMA_MODEL_NAME", default="model")
def serve(flama_model: str, flama_model_url: str, flama_model_name: str):
    """
    Serves an ML model within a Flama Application.
    """
    app = Flama()
    app.models.add_model(flama_model_url, model=flama_model, name=flama_model_name)
    uvicorn.run(app)
