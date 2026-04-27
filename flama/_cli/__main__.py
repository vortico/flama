import click

from flama._cli.commands.get import command as get_command
from flama._cli.commands.model import command as model_command
from flama._cli.commands.run import command as run_command
from flama._cli.commands.serve import command as serve_command
from flama._cli.commands.start import command as start_command
from flama._cli.formatting import FlamaGroup


@click.group(cls=FlamaGroup)
@click.version_option(
    package_name="Flama",
    message="Flama %(version)s",
    help="Check the version of your locally installed Flama",
)
@click.help_option(help="Get help about how to use Flama CLI")
def cli() -> None:
    """Fire up your models with Flama"""
    ...


cli.add_command(get_command)
cli.add_command(run_command)
cli.add_command(serve_command)
cli.add_command(start_command)
cli.add_command(model_command)


if __name__ == "__main__":
    cli()
