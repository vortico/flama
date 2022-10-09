import os

import click
import uvicorn

from flama import Flama


@click.command()
@click.argument("model-path", envvar="MODEL_PATH")
@click.argument("model-url", envvar="MODEL_URL", default="/")
@click.argument("model-name", envvar="MODEL_NAME", default="model")
@click.option("--app-name", envvar="APP_NAME", default="Flama", show_default=True)
@click.option("--app-version", envvar="APP_VERSION", default="0.1.0", show_default=True)
@click.option("--app-description", envvar="APP_DESCRIPTION", default="Fire up with the flame", show_default=True)
def serve(model_path: str, model_url: str, model_name: str, app_name: str, app_version: str, app_description: str):
    """
    Serves an ML model within a Flama App.
    """
    app = Flama(
        **{k: v for k, v in {"title": app_name, "version": app_version, "description": app_description}.items() if v}
    )
    app.models.add_model(model_url, model=model_path, name=model_name)  # type: ignore[attr-defined]
    uvicorn.run(app)
