import typing as t

import click

from flama.huggingface.module import HuggingFaceModule

__all__ = ["get", "command"]


@click.command(name="get", context_settings={"auto_envvar_prefix": "FLAMA"})
@click.argument("model-name")
@click.option("--source", type=click.Choice(["huggingface"]), required=True, help="Model source provider.")
@click.option("--task", default=None, help="Pipeline task (auto-detected from model card if omitted).")
@click.option(
    "--engine",
    type=click.Choice(["transformers", "vllm"]),
    default="transformers",
    help="Engine to use for serving (default: transformers).",
)
@click.option("-o", "--output", default=None, help="Output .flm path (default: <model-name>.flm).")
def command(model_name: str, source: str, task: str | None, engine: str, output: str | None):
    """Download and package a model as .flm.

    Download a model from a supported source and serialize it into Flama's .flm format, ready for serving with
    'flama model <path> run'.

    \b
    Example:
        flama get --source huggingface google/gemma-2-2b
        flama get --source huggingface --engine vllm google/gemma-2-2b
    """
    if source == "huggingface":
        result = HuggingFaceModule.get(
            model_name,
            output=output or f"{model_name.replace('/', '_')}.flm",
            task=task,
            engine=t.cast(t.Literal["transformers", "vllm"], engine),
        )
        click.echo(f"Model saved to {result}")
    else:
        raise click.BadParameter(f"Unknown source: {source}", param_hint="--source")


get = command
