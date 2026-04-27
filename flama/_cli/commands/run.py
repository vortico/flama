import click

from flama._cli.config.app import App
from flama._cli.config.config import Config
from flama._cli.config.config import options as config_options
from flama._cli.config.uvicorn import Uvicorn
from flama._cli.config.uvicorn import options as uvicorn_options
from flama._cli.formatting import FlamaCommand

__all__ = ["run", "command"]


@click.command(name="run", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.argument("flama-app", envvar="FLAMA_APP")
@config_options
@uvicorn_options
def command(flama_app: str, uvicorn: Uvicorn) -> None:
    """Run a Flama Application based on a route.

    <FLAMA_APP> is the route to the Flama object to be served, e.g. 'examples.hello_flama:app'. This can be passed
    directly as argument of the command line, or by environment variable."""
    Config(app=App.build(flama_app), server=uvicorn).run()


run = command.callback
