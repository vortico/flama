import asyncio
import functools
import json
import sys
import typing as t

import click

from flama._cli.formatting import CONSOLE, FlamaCommand, FlamaGroup
from flama._core.json_encoder import encode_json
from flama.models import ModelComponentBuilder
from flama.models.base import BaseLLMModel, BaseMLModel

if t.TYPE_CHECKING:
    from flama.models import ModelComponent

__all__ = ["model", "command"]


@click.group(name="model", cls=FlamaGroup)
@click.argument("flama-model-path", envvar="FLAMA_MODEL_PATH")
@click.pass_context
def command(ctx: click.Context, flama_model_path: str) -> None:
    """Interact with a packaged model without server.

    Works with both traditional ML models (sklearn, torch, tensorflow, transformers) and large language
    models (vllm). The artifact kind is auto-detected from its framework metadata; subcommands behave
    accordingly. To serve models over HTTP, use 'flama serve'.

    <FLAMA_MODEL_PATH> is the path of the model to be used, e.g. 'path/to/model.flm'. This can be passed
    directly as argument of the command line, or by environment variable.
    """
    try:
        ctx.obj = ModelComponentBuilder.build(flama_model_path)
    except FileNotFoundError:
        raise click.BadParameter("Model file not found.")


@command.command(name="inspect", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option("-p", "--pretty", is_flag=True, default=False, help="Pretty print the model inspection.")
@click.pass_obj
def inspect(model: "ModelComponent", pretty: bool) -> None:
    """Inspect a model artifact.

    Extracts the model metadata, including the ID, time when the model was created, information of the
    framework, and the model info; and the list of artifacts packaged with the model.
    """
    dump_func = encode_json
    if pretty:
        dump_func = functools.partial(encode_json, sort_keys=True, indent=4)

    CONSOLE.print(dump_func(model.model.inspect()).decode("utf-8"), highlight=False)


@command.command(name="run", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option(
    "-i",
    "--input",
    "input_str",
    type=str,
    default=None,
    help="Input as a literal string (typical for LLM prompts; for ML, a JSON list of feature vectors). "
    "Mutually exclusive with --file.",
)
@click.option(
    "-f",
    "--file",
    "input_file",
    type=click.File("r"),
    default=None,
    help="Read input from file. If neither --input nor --file is given, stdin is used.",
)
@click.option(
    "--param",
    multiple=True,
    help="Generation parameter as key=value (LLM only, repeatable).",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.File("w"),
    default="-",
    help="File to be used as output. (default: stdout).",
)
@click.option("-p", "--pretty", is_flag=True, default=False, help="Pretty print the output.")
@click.pass_obj
def run(
    model: "ModelComponent",
    input_str: str | None,
    input_file: t.IO[str] | None,
    param: tuple[str, ...],
    output_file: t.IO[str],
    pretty: bool,
) -> None:
    """Run a one-shot inference.

    For ML models, the input must be a JSON list of feature vectors and the output is a JSON list of
    predictions. For LLM models, the input is a prompt and the output is the generated response.

    \b
    Examples:
        echo '[[0, 0], [1, 1]]' | flama model model.flm run
        flama model model.flm run -f input.json
        flama model llm.flm run -i "What is Python?"
        flama model llm.flm run -i "Explain AI" --param temperature=0.7 --param max_tokens=100
    """
    raw = _read_input(input_str, input_file)

    if isinstance(model.model, BaseLLMModel):
        params = _parse_params(param)

        async def _query() -> t.Any:
            return await model.model.query(raw, **params)

        result = asyncio.run(_query())
    elif isinstance(model.model, BaseMLModel):
        if param:
            raise click.UsageError("--param is not supported for ML models.")
        result = model.model.predict(_decode_ml_json(raw))
    else:
        raise click.UsageError("Unsupported model type.")

    dump_func = functools.partial(encode_json, sort_keys=True, indent=4) if pretty else encode_json

    click.echo(dump_func(result).decode("utf-8"), output_file)


@command.command(name="stream", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option(
    "-i",
    "--input",
    "input_str",
    type=str,
    default=None,
    help="Input as a literal string (typical for LLM prompts; for ML, a JSON list of feature vectors). "
    "Mutually exclusive with --file.",
)
@click.option(
    "-f",
    "--file",
    "input_file",
    type=click.File("r"),
    default=None,
    help="Read input from file. If neither --input nor --file is given, stdin is used.",
)
@click.option(
    "--param",
    multiple=True,
    help="Generation parameter as key=value (LLM only, repeatable).",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.File("w"),
    default="-",
    help="File to be used as output for the stream. (default: stdout).",
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
def stream(
    model: "ModelComponent",
    input_str: str | None,
    input_file: t.IO[str] | None,
    param: tuple[str, ...],
    output_file: t.IO[str],
    buffered: bool,
) -> None:
    """Stream output from a model.

    For ML models, the input must be a JSON list of feature vectors and the model emits one output per
    item. For LLM models, the input is a prompt and the model emits one token at a time.

    \b
    Examples:
        echo '[[0, 0], [1, 1]]' | flama model model.flm stream
        flama model model.flm stream -f input.json --buffer
        flama model llm.flm stream -i "What is Python?"
        flama model llm.flm stream -i "Explain AI" --param temperature=0.7
    """
    raw = _read_input(input_str, input_file)

    if isinstance(model.model, BaseLLMModel):
        params = _parse_params(param)
        tokens = model.model.stream(raw, **params)
    elif isinstance(model.model, BaseMLModel):
        if param:
            raise click.UsageError("--param is not supported for ML models.")
        tokens = model.model.stream(_decode_ml_json(raw))
    else:
        raise click.UsageError("Unsupported model type.")

    async def _encoded() -> t.AsyncIterator[str]:
        async for item in tokens:
            yield encode_json(item, compact=True).decode()

    async def _run() -> None:
        if buffered:
            click.echo("".join([token async for token in _encoded()]), file=output_file)
        else:
            async for token in _encoded():
                click.echo(token, file=output_file, nl=False)
            if output_file.name != "<stdout>":
                click.echo("", file=output_file)

    asyncio.run(_run())


def _decode_ml_json(raw: str) -> t.Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise click.BadParameter("Input must be valid JSON for ML models.")


def _read_input(input_str: str | None, input_file: t.IO[str] | None) -> str:
    """Resolve the raw input string from the mutually-exclusive ``-i``/``-f`` options.

    Falls back to stdin when neither is provided.
    """
    if input_str is not None and input_file is not None:
        raise click.UsageError("--input and --file are mutually exclusive.")
    if input_str is not None:
        return input_str
    if input_file is not None:
        return input_file.read()
    return sys.stdin.read()


def _parse_params(param: tuple[str, ...]) -> dict[str, t.Any]:
    params: dict[str, t.Any] = {}
    for p in param:
        if "=" not in p:
            raise click.BadParameter(f"Parameter must be in key=value format: {p}", param_hint="--param")
        key, value = p.split("=", 1)
        try:
            params[key] = json.loads(value)
        except json.JSONDecodeError:
            params[key] = value
    return params


model = command.callback
