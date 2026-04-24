import asyncio
import pathlib
import struct
import tempfile
import typing as t

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from flama import exceptions
from flama._core.json_encoder import encode_json
from flama.serialize.compression import Compression
from flama.serialize.data_structures import ModelArtifact
from flama.serialize.model_serializers import ModelSerializer

try:
    from flama.client import _BaseClient
except exceptions.DependencyNotInstalled:  # pragma: no cover
    _BaseClient = None  # ty: ignore[invalid-assignment]

__all__ = ["get", "command"]

HF_BASE_URL = "https://huggingface.co"

_FILE_HEADER_FORMAT: t.Final[str] = "!I I Q"
_BODY_HEADER_FORMAT: t.Final[str] = "!Q Q I Q"

console = Console()


async def _download_model(model_name: str, local_dir: pathlib.Path) -> str | None:
    """Download all files from a HuggingFace model repository.

    Uses the HuggingFace Hub REST API directly via ``_BaseClient`` to stream-download each file with a rich progress
    bar showing real byte-level progress.

    :param model_name: HuggingFace model identifier (e.g. ``"Qwen/Qwen2.5-0.5B"``).
    :param local_dir: Local directory to download files into.
    :return: The ``pipeline_tag`` from the model card, or ``None`` if not set.
    """
    if _BaseClient is None:  # noqa
        raise click.ClickException("httpx is required for downloading models. Install with: pip install flama[client]")

    async with _BaseClient(base_url=HF_BASE_URL, follow_redirects=True) as client:
        resp = await client.get(f"/api/models/{model_name}")
        resp.raise_for_status()
        info = resp.json()

        pipeline_tag: str | None = info.get("pipeline_tag")
        files: list[str] = [s["rfilename"] for s in info.get("siblings", [])]
        total_size: int = info.get("usedStorage") or 0

        with Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            dl = progress.add_task("Downloading", total=total_size)

            for filename in files:
                dest = local_dir / filename
                dest.parent.mkdir(parents=True, exist_ok=True)

                async with client.stream("GET", f"/{model_name}/resolve/main/{filename}") as stream:
                    stream.raise_for_status()
                    with dest.open("wb") as f:
                        async for chunk in stream.aiter_bytes(chunk_size=64 * 1024):
                            f.write(chunk)
                            progress.update(dl, advance=len(chunk))

    return pipeline_tag


def _package_model(
    local_dir: pathlib.Path,
    output_path: pathlib.Path,
    *,
    task: str | None,
    model_name: str,
    engine: t.Literal["transformers", "vllm"],
) -> None:
    """Archive, compress and write a downloaded model directory as ``.flm``.

    :param local_dir: Directory containing the downloaded model files.
    :param output_path: Destination path for the ``.flm`` file.
    :param task: Pipeline task name (e.g. ``"text-generation"``).
    :param model_name: Original model identifier for metadata.
    :param engine: Serialization engine.
    """
    with console.status("Archiving..."):
        model_tar = ModelSerializer.from_lib(engine).dump(local_dir)

    with console.status("Compressing..."):
        c = Compression("zstd")
        artifact = ModelArtifact.from_model(
            local_dir,
            config={"task": task},
            extra={"model_name": model_name},
            lib=engine,
        )
        meta = c.compress(encode_json(artifact.meta.to_dict(), compact=True))
        model = c.compress(model_tar)

        body_header = struct.pack(_BODY_HEADER_FORMAT, len(meta), len(model), 0, 0)
        body = b"".join((body_header, meta, model))
        file_header = struct.pack(_FILE_HEADER_FORMAT, 1, c.format, len(body))

        with output_path.open("wb") as f:
            f.write(file_header)
            f.write(body)


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
    'flama llm <path> run'.

    \b
    Example:
        flama get --source huggingface Qwen/Qwen2.5-0.5B
        flama get --source huggingface --engine vllm Qwen/Qwen2.5-0.5B
    """
    if source != "huggingface":
        raise click.BadParameter(f"Unknown source: {source}", param_hint="--source")

    output_path = pathlib.Path(output or f"{model_name.replace('/', '_')}.flm")

    with tempfile.TemporaryDirectory() as tmp:
        local_dir = pathlib.Path(tmp)

        pipeline_tag = asyncio.run(_download_model(model_name, local_dir))
        if task is None:
            task = pipeline_tag

        _package_model(
            local_dir,
            output_path,
            task=task,
            model_name=model_name,
            engine=t.cast(t.Literal["transformers", "vllm"], engine),
        )

    console.print(f"Model saved to [bold]{output_path}[/bold]")


get = command
