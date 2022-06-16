import click
import subprocess
import shlex
import uvicorn


from flama import Flama


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
@click.option("-d", "--dev", envvar="FLAMA_DEV", is_flag=True, help="Development mode.")
def run(flama_app: str, dev: bool):
    """
    Runs a Flama Application.

    FLAMA_APP is the path to the Flama object to be served, e.g. examples.hello_flama:app
    """
    command = shlex.split(f"uvicorn {flama_app}")
    if dev:
        command += ["--reload"]

    subprocess.run(command)


cli.add_command(run)


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


cli.add_command(serve)


if __name__ == "__main__":
    cli()
