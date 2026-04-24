import asyncio
import functools
import json
import typing as t

import click

from flama._core.json_encoder import encode_json
from flama.cli.config.config import Config
from flama.cli.config.uvicorn import Uvicorn
from flama.cli.config.uvicorn import options as uvicorn_options
from flama.models import ModelComponentBuilder
from flama.models.base import BaseLLMModel

if t.TYPE_CHECKING:
    pass

__all__ = ["llm", "command"]


@click.group(name="llm")
@click.argument("flama-model-path", envvar="FLAMA_MODEL_PATH")
@click.pass_context
def command(ctx: click.Context, flama_model_path: str):
    """Interact with an LLM.

    This command is used to directly interact with an LLM. This command can be used to perform any operation that is
    supported by the model, such as inspect, configure, query, stream, or run a server with a chat UI.
    <FLAMA_MODEL_PATH> is the path of the model to be used, e.g. 'path/to/model.flm'. This can be passed
    directly as argument of the command line, or by environment variable.
    """
    ctx.ensure_object(dict)
    ctx.obj["model_path"] = flama_model_path

    if ctx.invoked_subcommand != "run":
        try:
            ctx.obj["component"] = ModelComponentBuilder.load(flama_model_path)
        except FileNotFoundError:
            raise click.BadParameter("Model file not found.")


@command.command(name="run", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option("--name", default="llm", show_default=True, help="Name for the LLM resource.")
@click.option("--path", "url_path", default="/", show_default=True, help="URL path for the LLM resource.")
@uvicorn_options
@click.pass_context
def run(ctx: click.Context, name: str, url_path: str, uvicorn: Uvicorn):
    """Serve an LLM with a web chat UI.

    Start a Flama server exposing the LLM with inspect, configure, query, stream and chat endpoints.

    \b
    Examples:
        flama llm model.flm run
        flama llm model.flm run --server-port 8080
        flama llm model.flm run --path /my-llm/ --name my-model
    """
    from flama import Flama
    from flama.cli.config.app import FlamaApp

    model_path = ctx.obj["model_path"]

    app = Flama(
        openapi={
            "info": {
                "title": f"Flama LLM – {name}",
                "version": "0.1.0",
                "description": f"LLM served from {model_path}",
            }
        },
        schema="/schema/",
        docs="/docs/",
    )
    app.models.add_llm(path=url_path, model=model_path, name=name)

    Config(app=FlamaApp(app=app), server=uvicorn).run()


@command.command(name="inspect", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option("-p", "--pretty", is_flag=True, default=False, help="Pretty print the model inspection.")
@click.pass_context
def inspect(ctx: click.Context, pretty: bool):
    """Inspect an LLM.

    This command is used to inspect an LLM without the need of a server. This command can be used to extract the
    model metadata, including the ID, time when the model was created, information of the
    framework, and the model info; and the list of artifacts packaged with the model.
    """
    model = ctx.obj["component"]
    dump_func = encode_json
    if pretty:
        dump_func = functools.partial(encode_json, sort_keys=True, indent=4)

    click.echo(dump_func(model.model.inspect()).decode("utf-8"))


@command.command(name="configure", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option(
    "--param",
    multiple=True,
    help="Generation parameter as key=value (repeatable).",
)
@click.option("--pretty", is_flag=True, default=False, help="Pretty print the output.")
@click.pass_context
def configure(ctx: click.Context, param: tuple[str, ...], pretty: bool):
    """Configure default generation parameters for an LLM.

    Set default parameters that will be used for all subsequent queries and streams unless overridden per-request.

    \b
    Example:
        flama llm model.flm configure --param temperature=0.7 --param max_tokens=100
    """
    model = ctx.obj["component"]
    if not isinstance(model.model, BaseLLMModel):
        raise click.UsageError("This command requires an LLM model (loaded with engine=vllm).")

    params = _parse_params(param)
    model.model.configure(params)

    dump_func = encode_json
    if pretty:
        dump_func = functools.partial(encode_json, sort_keys=True, indent=4)

    click.echo(dump_func(model.model.params).decode("utf-8"))


@command.command(name="query", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option("-p", "--prompt", required=True, help="Prompt to send to the LLM.")
@click.option(
    "--param",
    multiple=True,
    help="Generation parameter as key=value (repeatable).",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.File("w"),
    default="-",
    help="File to be used as output. (default: stdout).",
)
@click.option("--pretty", is_flag=True, default=False, help="Pretty print the output.")
@click.pass_context
def query(ctx: click.Context, prompt: str, param: tuple[str, ...], output_file, pretty: bool):
    """Query an LLM.

    Send a prompt to an LLM and get a buffered response without the need of a server.

    \b
    Example:
        flama llm model.flm query -p "What is Python?"
        flama llm model.flm query -p "Explain AI" --param temperature=0.7 --param max_tokens=100
    """
    model = ctx.obj["component"]
    if not isinstance(model.model, BaseLLMModel):
        raise click.UsageError("This command requires an LLM model (loaded with engine=vllm).")

    params = _parse_params(param)

    async def _run():
        return await model.model.query(prompt, **params)

    result = asyncio.run(_run())

    dump_func = encode_json
    if pretty:
        dump_func = functools.partial(encode_json, sort_keys=True, indent=4)

    click.echo(dump_func(result).decode("utf-8"), output_file)


@command.command(name="stream", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option("-p", "--prompt", required=True, help="Prompt to send to the LLM.")
@click.option(
    "--param",
    multiple=True,
    help="Generation parameter as key=value (repeatable).",
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
@click.pass_context
def stream(ctx: click.Context, prompt: str, param: tuple[str, ...], output_file, buffered: bool):
    """Stream output from an LLM.

    Send a prompt to an LLM and stream the response token by token.

    \b
    Examples:
        flama llm model.flm stream -p "What is Python?"
        flama llm model.flm stream -p "Explain AI" --param temperature=0.7
        flama llm model.flm stream -p "Hello" --buffer
    """
    model = ctx.obj["component"]
    if not isinstance(model.model, BaseLLMModel):
        raise click.UsageError("This command requires an LLM model (loaded with engine=vllm).")

    params = _parse_params(param)

    async def _run():
        chunks: list[str] = []
        async for item in model.model.stream(prompt, **params):
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


llm = command.callback
