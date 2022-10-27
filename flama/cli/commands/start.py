import click

from flama.cli.config.config import Config, ExampleConfig

__all__ = ["start", "command"]


@click.command(name="start", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.argument("flama-config", envvar="FLAMA_CONFIG", default="flama.json")
@click.option(
    "--create-config",
    type=click.Choice(["simple", "full"], case_sensitive=False),
    help="Create a config file: 'simple' only includes the host and port of the webserver; 'full' "
    "includes all the details of the webserver.",
)
def command(flama_config: str, create_config: str):
    """
    Start a Flama Application with the configuration specified in <FLAMA_CONFIG>
    """
    if create_config:
        with open(flama_config, "w") as fs:
            fs.write(ExampleConfig.build(mode=create_config).dumps())
        return

    with open(flama_config, "r") as fs:
        config = Config.load(fs)  # type: ignore[arg-type]

    config.run()


start = command.callback
