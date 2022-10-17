import click
import uvicorn

from flama import Flama


@click.command()
@click.argument("model-path", envvar="FLAMA_MODEL_PATH")
@click.option("--model-url", envvar="FLAMA_MODEL_URL", default="/", show_default=True, help="Route of the model")
@click.option("--model-name", envvar="FLAMA_MODEL_NAME", default="model", show_default=True, help="Name of the model")
@click.option(
    "--app-title", envvar="FLAMA_APP_TITLE", default="Flama", show_default=True, help="Name of the application")
@click.option(
    "--app-version", envvar="FLAMA_APP_VERSION", default="0.1.0", show_default=True, help="Version of the application"
)
@click.option(
    "--app-description",
    envvar="FLAMA_APP_DESCRIPTION",
    default="Fire up with the flame",
    show_default=True,
    help="Description of the application",
)
def serve(model_path: str, model_url: str, model_name: str, app_title: str, app_version: str, app_description: str):
    """
    Serve the ML model file at <MODEL_PATH> within a Flama Application.
    """
    app = Flama(
        **{k: v for k, v in {"title": app_title, "version": app_version, "description": app_description}.items() if v}
    )
    app.models.add_model(model_url, model=model_path, name=model_name)  # type: ignore[attr-defined]
    uvicorn.run(app)
