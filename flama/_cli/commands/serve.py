import click

from flama._cli.config.app import App
from flama._cli.config.app import options as app_options
from flama._cli.config.config import Config
from flama._cli.config.config import options as config_options
from flama._cli.config.uvicorn import Uvicorn
from flama._cli.config.uvicorn import options as uvicorn_options
from flama._cli.formatting import FlamaCommand

__all__ = ["serve", "command"]


@click.command(name="serve", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@config_options
@app_options
@uvicorn_options
def command(app: App, uvicorn: Uvicorn) -> None:
    """Serve an ML model file within a Flama Application.

    Serve the ML model file specified by <MODEL_PATH> within a Flama Application."""
    Config(app=app, server=uvicorn).run()


serve = command.callback
