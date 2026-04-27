import asyncio
import functools
import json
import typing as t

import click

from flama._cli.formatting import CONSOLE, FlamaCommand, FlamaGroup
from flama._core.json_encoder import encode_json
from flama.models import MLModelComponentBuilder
from flama.models.base import BaseMLModel

if t.TYPE_CHECKING:
    from flama.models import ModelComponent

__all__ = ["model", "command"]


@click.group(name="model", cls=FlamaGroup)
@click.argument("flama-model-path", envvar="FLAMA_MODEL_PATH")
@click.pass_context
def command(ctx: click.Context, flama_model_path: str) -> None:
    """Interact with an ML model without server.

    This command is used to directly interact with an ML model without the need of a server. This command can be used
    to perform any operation that is supported by the model, such as inspect, predict, or stream.
    <FLAMA_MODEL_PATH> is the path of the model to be used, e.g. 'path/to/model.flm'. This can be passed
    directly as argument of the command line, or by environment variable.
    """
    try:
        ctx.obj = MLModelComponentBuilder.load(flama_model_path)
    except FileNotFoundError:
        raise click.BadParameter("Model file not found.")


@command.command(name="inspect", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option("-p", "--pretty", is_flag=True, default=False, help="Pretty print the model inspection.")
@click.pass_obj
def inspect(model: "ModelComponent", pretty: bool) -> None:
    """Inspect an ML model.

    This command is used to inspect an ML model without the need of a server. This command can be used to extract the
    ML model metadata, including the ID, time when the model was created, information of the
    framework, and the model info; and the list of artifacts packaged with the model.
    """
    dump_func = encode_json
    if pretty:
        dump_func = functools.partial(encode_json, sort_keys=True, indent=4)

    CONSOLE.print(dump_func(model.model.inspect()).decode("utf-8"), highlight=False)


@command.command(name="predict", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
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
@click.option("-p", "--pretty", is_flag=True, default=False, help="Pretty print the model prediction.")
@click.pass_obj
def predict(model: "ModelComponent", input_file, output_file, pretty: bool) -> None:
    """Make a prediction using an ML model.

    This command is used to make a prediction using an ML model without the need of a server. It can be used for
    batch predictions, so both input and output arguments must be json files containing a list of input values, each
    input value being a list of values associated to the input of the model. The output will be the list of predictions
    associated to the input, with each prediction being a list of values representing the output of the model.

    \b
    Example:
        input.json: [[0, 0], [0, 1], [1, 0], [1, 1]]
        output.json: [[0], [1], [1], [0]]
    """
    if not isinstance(model.model, BaseMLModel):
        raise click.UsageError("This command requires an ML model (sklearn, torch, tensorflow, or transformers).")

    try:
        data = json.load(input_file)
    except json.JSONDecodeError:
        raise click.BadParameter("Input file must be a valid json file.")

    dump_func = encode_json
    if pretty:
        dump_func = functools.partial(encode_json, sort_keys=True, indent=4)

    click.echo(dump_func(model.model.predict(data)).decode("utf-8"), output_file)


@command.command(name="stream", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option(
    "-f",
    "--file",
    "input_file",
    type=click.File("r"),
    default="-",
    help="File to be used as input for the model stream in JSON format. (default: stdin).",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.File("w"),
    default="-",
    help="File to be used as output for the model stream. (default: stdout).",
)
@click.option(
    "-b",
    "--buffer",
    "buffered",
    is_flag=True,
    default=False,
    help="Buffer all output and write at once instead of streaming.",
)
@click.pass_obj
def stream(model: "ModelComponent", input_file, output_file, buffered: bool) -> None:
    """Stream output from an ML model.

    Provide input data via -f/--file (or stdin) in JSON format.

    \b
    Examples:
        echo '[[0, 0], [1, 1]]' | flama model model.flm stream
        flama model model.flm stream -f input.json --buffer
    """
    if not isinstance(model.model, BaseMLModel):
        raise click.UsageError("This command requires an ML model (sklearn, torch, tensorflow, or transformers).")

    try:
        data = json.load(input_file)
    except json.JSONDecodeError:
        raise click.BadParameter("Input file must be a valid json file.")

    async def _input():
        for item in data:
            yield item

    async def _run():
        chunks: list[str] = []
        async for item in model.model.stream(_input()):
            token = encode_json(item, compact=True).decode()
            if buffered:
                chunks.append(token)
            else:
                click.echo(token, file=output_file, nl=False)
        if buffered:
            click.echo("".join(chunks), file=output_file)
        elif output_file.name != "<stdout>":
            click.echo("", file=output_file)

    asyncio.run(_run())


model = command.callback
