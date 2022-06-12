import click
import typing
import subprocess
import shlex


def uvicorn(*args) -> typing.List[str]:
    return shlex.split("uvicorn") + list(args)


@click.group()
@click.version_option(
    package_name="Flama",
    help="Check the version of your locally installed Flama",
)
@click.help_option(help="Get help about how to use Flama CLI")
def cli():
    """
    Fire up your models with Flama 🔥
    """
    ...


@click.command()
@click.argument("flama-app", envvar="FLAMA_APP")
def run(flama_app: str):
    """
    Run an API.

    FLAMA_APP is the path to the Flama object to be served, e.g. examples.hello_flama:app
    """
    subprocess.run(uvicorn(flama_app))


cli.add_command(run)


@click.command()
@click.argument("flama-app", envvar="FLAMA_APP")
def dev(flama_app: str):
    """
    Run an API in development mode.
    """
    subprocess.run(uvicorn(flama_app, "--reload"))


cli.add_command(dev)


@click.command()
def serve():
    """
    Run an API for a ML Model.
    """
    ...


cli.add_command(serve)


if __name__ == "__main__":
    cli()
