import click

from flama.cli.config.app import App
from flama.cli.config.config import Config
from flama.cli.config.config import options as config_options
from flama.cli.config.uvicorn import Uvicorn
from flama.cli.config.uvicorn import options as uvicorn_options

__all__ = ["run", "command"]


@click.command(name="run", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.argument("flama-app", envvar="FLAMA_APP")
@config_options
@uvicorn_options
def command(flama_app: str, dev: bool, uvicorn: Uvicorn):
    """
    Run a Flama Application.

    <FLAMA_APP> is the route to the Flama object to be served, e.g. 'examples.hello_flama:app'. This can be passed
    directly as argument of the command line, or by environment variable.
    """
    Config(dev=dev, app=App.build(flama_app), server=uvicorn).run()


run = command.callback
