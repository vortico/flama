import click
import uvicorn


@click.command()
@click.argument("flama-app", envvar="FLAMA_APP")
@click.option("-d", "--dev", envvar="FLAMA_DEV", is_flag=True, help="Development mode.")
def run(flama_app: str, dev: bool):
    """
    Run a Flama Application.

    <FLAMA_APP> is the route to the Flama object to be served, e.g. 'examples.hello_flama:app'. This can be passed
    directly as argument of the command line, or by environment variable.
    """
    uvicorn.run(flama_app, reload=dev)
