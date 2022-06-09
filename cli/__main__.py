import click


@click.group()
def cli():
    """
    Flama 🔥.
    """
    ...


@click.command()
def run():
    """
    Run an API.
    """
    ...


cli.add_command(run)


@click.command()
def dev():
    """
    Run an API in development mode.
    """
    ...


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
