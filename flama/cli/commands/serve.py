import click

from flama.cli.config.app import App
from flama.cli.config.app import options as app_options
from flama.cli.config.config import Config
from flama.cli.config.config import options as config_options
from flama.cli.config.uvicorn import Uvicorn
from flama.cli.config.uvicorn import options as uvicorn_options

__all__ = ["serve", "command"]


@click.command(name="serve", context_settings={"auto_envvar_prefix": "FLAMA"})
@config_options
@app_options
@uvicorn_options
def command(app: App, uvicorn: Uvicorn):
    """
    Serve the ML model file <MODEL_PATH> within a Flama Application.
    """
    Config(app=app, server=uvicorn).run()


serve = command.callback
