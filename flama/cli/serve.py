import click
import uvicorn

from flama import Flama


@click.command(context_settings={"auto_envvar_prefix": "FLAMA"})
@click.argument("model-path", envvar="FLAMA_MODEL_PATH")
@click.option("--model-url", envvar="MODEL_URL", default="/", show_default=True, help="Route of the model")
@click.option("--model-name", envvar="MODEL_NAME", default="model", show_default=True, help="Name of the model")
@click.option("--app-title", envvar="APP_TITLE", default="Flama", show_default=True, help="Name of the application")
@click.option(
    "--app-version", envvar="APP_VERSION", default="0.1.0", show_default=True, help="Version of the application"
)
@click.option(
    "--app-description",
    envvar="FLAMA_APP_DESCRIPTION",
    default="Fire up with the flame",
    show_default=True,
    help="Description of the application",
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    envvar="HOST",
    help="Bind socket to this host.",
    show_default=True,
)
@click.option(
    "--port",
    type=int,
    default=8000,
    envvar="PORT",
    help="Bind socket to this port.",
    show_default=True,
)
def serve(
    model_path: str,
    model_url: str,
    model_name: str,
    app_title: str,
    app_version: str,
    app_description: str,
    host: str,
    port: int,
):
    """
    Serve the ML model file at <MODEL_PATH> within a Flama Application.
    """
    app = Flama(
        **{k: v for k, v in {"title": app_title, "version": app_version, "description": app_description}.items() if v}
    )
    app.models.add_model(model_url, model=model_path, name=model_name)  # type: ignore[attr-defined]

    uvicorn.run(
        app,
        host=host,
        port=port,
    )
