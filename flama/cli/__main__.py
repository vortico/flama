import click

from flama.cli.run import run
from flama.cli.serve import serve
from flama.cli.start import start


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


cli.add_command(run)
cli.add_command(serve)
cli.add_command(start)


if __name__ == "__main__":
    cli()
