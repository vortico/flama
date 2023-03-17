import functools
import json

import click

from flama.http import EnhancedJSONEncoder
from flama.models import ModelComponentBuilder

__all__ = ["model", "command"]


@click.group(name="model")
@click.argument("model-path", envvar="FLAMA_MODEL_PATH")
def command(model_path: str):
    """Interact with an ML model without server.

    This command is used to directly interact with an ML model without the need of a server. This command can be used
    to perform any operation that is supported by the model, such as inspect, or predict.
    <FLAMA_MODEL_PATH> is the path of the model to be used, e.g. 'path/to/model.flm'. This can be passed
    directly as argument of the command line, or by environment variable.
    """
    ...


@command.command(name="inspect", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option("-p", "--pretty", is_flag=True, default=False, help="Pretty print the model inspection.")
@click.pass_context
def inspect(ctx: click.Context, pretty: bool):
    """Inspect an ML model.

    This command is used to inspect an ML model without the need of a server. This command can be used to extract the
    ML model metadata, including the ID, time when the model was created, information of the
    framework, and the model info; and the list of artifacts packaged with the model.
    """
    try:
        model = ModelComponentBuilder.load(ctx.parent.params["model_path"])  # type: ignore[union-attr]
    except FileNotFoundError:
        raise click.BadParameter("Model file not found.")

    dump_func = functools.partial(json.dumps, cls=EnhancedJSONEncoder)
    if pretty:
        dump_func = functools.partial(dump_func, sort_keys=True, indent=4)

    click.echo(dump_func(model.model.inspect()))


@command.command(name="predict", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option(
    "-f",
    "--file",
    "input_file",
    type=click.File("r"),
    default="-",
    help="File to be used as input for the model prediction in JSON format. (default: stdin).",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.File("w"),
    default="-",
    help="File to be used as output for the model prediction in JSON format. (default: stdout).",
)
@click.option("-p", "--pretty", is_flag=True, default=False, help="Pretty print the model inspection.")
@click.pass_context
def predict(ctx: click.Context, input_file, output_file, pretty: bool):
    """Make a prediction using an ML model.

    This command is used to make a prediction using an ML model without the need of a server. It can be used for
    batch predictions, so both input and output arguments must be json files containing a list of input values, each
    input value being a list of values associated to the input of the model. The output will be the list of predictions
    associated to the input, with each prediction being a list of values representing the output of the model.

    Example:

    - input.json:
    [[0, 0], [0, 1], [1, 0], [1, 1]]

    - output.json:
    [[0], [1], [1], [0]]
    """
    try:
        model = ModelComponentBuilder.load(ctx.parent.params["model_path"])  # type: ignore[union-attr]
    except FileNotFoundError:
        raise click.BadParameter("Model file not found.")

    try:
        data = json.load(input_file)
    except json.JSONDecodeError:
        raise click.BadParameter("Input file must be a valid json file.")

    dump_func = functools.partial(json.dumps, cls=EnhancedJSONEncoder)
    if pretty:
        dump_func = functools.partial(dump_func, sort_keys=True, indent=4)

    click.echo(dump_func(model.model.predict(data)), output_file)


model = command.callback
