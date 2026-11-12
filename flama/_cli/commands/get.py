import abc
import asyncio
import dataclasses
import pathlib
import random
import tempfile
import typing as t
from types import TracebackType

import click
import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from flama import _concurrency, _imports, _io, types
from flama._cli.formatting import CONSOLE, FlamaCommand
from flama.client import Client
from flama.serialize.exceptions import UnsafeArtifactPath
from flama.serialize.serializer import Serializer

__all__ = ["get", "command"]


@dataclasses.dataclass(frozen=True)
class _RetryPolicy:
    """Bounded exponential backoff with jitter for transient HTTP failures.

    A retry policy is a callable that drives a coroutine factory through up to
    ``attempts`` invocations, sleeping ``min(max_delay, base_delay * 2**(n-1))``
    plus uniform jitter between failed attempts. Permanent errors short-circuit
    the loop via :meth:`is_transient`.

    :param attempts: Total number of attempts (including the first).
    :param base_delay: Initial backoff delay in seconds.
    :param max_delay: Upper bound for backoff delay.
    """

    attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0

    @staticmethod
    def is_transient(exc: BaseException) -> bool:
        """Return ``True`` for retry-worthy transport / 5xx / 429 errors."""
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            return status == 429 or 500 <= status < 600
        return isinstance(exc, httpx.RequestError)

    async def __call__(self, fn: t.Callable[[], t.Awaitable[None]]) -> None:
        """Invoke *fn* with bounded exponential backoff + jitter on transient errors.

        :param fn: Zero-arg coroutine factory. A new coroutine is built per attempt.
        """
        for attempt in range(1, self.attempts + 1):
            try:
                await fn()
                return
            except Exception as exc:
                if not self.is_transient(exc) or attempt == self.attempts:
                    raise
                delay = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
                await asyncio.sleep(delay + random.uniform(0, delay * 0.5))


@dataclasses.dataclass(frozen=True)
class _Inspection:
    """What a source publishes for a model, and how it is packaged.

    :param lib: Framework to package for.
    :param files: Files to download, with their sizes.
    :param config: Framework configuration recorded in the manifest.
    """

    lib: types.ModelLib
    files: dict[str, int]
    config: dict[str, t.Any] = dataclasses.field(default_factory=dict)


class _Downloader(abc.ABC):
    """Download a model from a remote source and package it into a ``.flm`` artifact.

    Subclasses inspect what the source publishes and download its files. Checking the framework, staging and
    packaging are shared, so nothing is downloaded for a model that cannot be packaged.

    :param model_name: Source-specific model identifier.
    :param output: Destination ``.flm`` path.
    :param family: Artifact family recorded in the manifest. LLM artifacts are run by vLLM or MLX at load time,
        whatever framework they are packaged for.
    """

    def __init__(self, model_name: str, output: pathlib.Path, family: types.ModelFamily) -> None:
        self.model_name = model_name
        self.output = output
        self.family: types.ModelFamily = family
        self.extra: dict[str, str] = {"model_name": self.model_name}
        self.tmp = tempfile.TemporaryDirectory()

    async def run(self) -> None:
        """Download to a temporary directory and package the result as ``.flm``.

        :raises DependencyNotInstalled: If the framework to package for is not installed, before any file is
            downloaded.
        """
        async with self:
            inspection = await self._inspect()
            _imports.Dependency(inspection.lib).require()
            await self._download(inspection.files)
            self._pack(inspection)

        CONSOLE.print(f"Model saved to [bold]{self.output}[/bold]")

    @abc.abstractmethod
    async def _inspect(self) -> _Inspection:
        """Read what the source publishes for the model, refusing what cannot be packaged.

        :return: How the model is packaged.
        :raises click.ClickException: If the model cannot be packaged.
        """
        ...

    @abc.abstractmethod
    async def _download(self, files: dict[str, int]) -> None:
        """Download files into the staging directory.

        :param files: Files to download, with their sizes.
        """
        ...

    def _pack(self, inspection: _Inspection) -> None:
        with CONSOLE.status("Packaging..."):
            Serializer.dump(
                self.tmp.name,
                path=self.output,
                family=self.family,
                lib=inspection.lib,
                config=inspection.config,
                extra=self.extra,
            )

    async def __aenter__(self) -> "_Downloader":
        self.tmp.__enter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        self.tmp.__exit__(exc_type, exc_value, traceback)
        return None


class _HuggingFaceDownloader(_Downloader):
    """Download a model from the HuggingFace Hub.

    Uses the Hub REST API via :class:`~flama.client.Client` (HTTP/2 multiplexed) to stream
    each file concurrently. Up to ``max_concurrent`` files are fetched in parallel; each
    file is streamed to a ``<dest>.tmp`` and atomically renamed on success. Transient
    failures (network errors, HTTP 429/5xx) are retried with exponential backoff + jitter.

    :param model_name: HuggingFace model identifier (e.g. ``"Qwen/Qwen2.5-0.5B"``).
    :param output: Destination ``.flm`` path.
    :param max_concurrent: Maximum number of files to download in parallel.
    """

    BASE_URL: t.ClassVar[str] = "https://huggingface.co"

    def __init__(
        self, model_name: str, output: pathlib.Path, family: types.ModelFamily, *, max_concurrent: int
    ) -> None:
        super().__init__(model_name, output, family)
        self.client = Client(base_url=self.BASE_URL, follow_redirects=True, http2=True)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.retry = _RetryPolicy()

    async def _inspect(self) -> _Inspection:
        response = await self.client.get(f"/api/models/{self.model_name}", params={"blobs": "true"})
        response.raise_for_status()
        info = response.json()

        # Transformers checkpoints declare a model type whatever library the Hub labels them with, e.g. MLX conversions.
        if not (info.get("config") or {}).get("model_type"):
            raise click.ClickException(
                f"'{self.model_name}' is not a transformers model (the Hub reports it as "
                f"'{info.get('library_name') or 'unknown'}'), so it cannot be packaged"
            )

        return _Inspection(
            lib="transformers",
            files={s["rfilename"]: s.get("size", 0) for s in info.get("siblings", [])},
            config={"task": info.get("pipeline_tag")},
        )

    async def _download(self, files: dict[str, int]) -> None:
        with Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=CONSOLE,
        ) as progress:
            progress_id = progress.add_task("Downloading", total=sum(files.values()))

            tasks = await _concurrency.run_task_group(
                *(self._download_file(name, progress, progress_id) for name in files)
            )
            for task in tasks:
                task.result()

    async def _download_file(self, filename: str, progress: Progress, progress_id: TaskID) -> None:
        """Stage *filename* under the download directory, refusing names that escape it.

        Remote file names come from the source's own API listing, so they are attacker-controlled
        for any third-party repository; the resolved destination is confined to the staging root
        (``CWE-22``).

        :raises UnsafeArtifactPath: When *filename* resolves outside the staging directory.
        """
        async with self.semaphore:
            root = pathlib.Path(self.tmp.name).resolve()
            dest = (root / filename).resolve()
            if not dest.is_relative_to(root):
                raise UnsafeArtifactPath(filename)

            await _concurrency.run(dest.parent.mkdir, parents=True, exist_ok=True)
            await self.retry(lambda: self._stream_to_file(filename, dest, progress, progress_id))

    async def _stream_to_file(self, filename: str, dest: pathlib.Path, progress: Progress, progress_id: TaskID) -> None:
        written = 0
        try:
            async with self.client.stream("GET", f"/{self.model_name}/resolve/main/{filename}") as stream:
                stream.raise_for_status()
                # The staging directory is discarded after packaging, so there is no need to sync each file to disk.
                with _io.AtomicFile(dest, durable=False) as f:
                    async for chunk in stream.aiter_bytes(chunk_size=60 * 2**10):
                        await _concurrency.run(f.write, chunk)
                        written += len(chunk)
                        progress.update(progress_id, advance=len(chunk))
        except BaseException:
            if written:
                progress.update(progress_id, advance=-written)
            raise

    async def __aenter__(self) -> "_Downloader":
        await super().__aenter__()
        await self.client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        await self.client.__aexit__(exc_type, exc_value, traceback)
        return await super().__aexit__(exc_type, exc_value, traceback)


@click.command(name="get", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.argument("model-name")
@click.option("--source", type=click.Choice(["huggingface"]), required=True, help="Model source provider.")
@click.option(
    "--family",
    type=click.Choice(t.get_args(types.ModelFamily)),
    required=True,
    help="Artifact family recorded in the manifest. Use 'ml' for traditional ML models and 'llm' for large language "
    "models. The choice is persisted in the .flm manifest and drives runtime dispatch at load time; it cannot be "
    "changed without repacking.",
)
@click.option("-o", "--output", default=None, help="Output .flm path (default: <model-name>.flm).")
@click.option(
    "--max-concurrent",
    type=click.IntRange(min=1),
    default=8,
    show_default=True,
    help="Maximum number of files to download concurrently.",
)
def command(model_name: str, source: str, family: types.ModelFamily, output: str | None, max_concurrent: int) -> None:
    """Download and package a model as .flm.

    Download a model from a supported source and serialize it into Flama's .flm format, ready for serving with
    'flama serve' or interaction with 'flama model'. The artifact family must be declared explicitly via
    ``--family``: ML artifacts run through the framework recorded in the manifest, while LLM artifacts are
    dispatched to vLLM or MLX at load time depending on what is installed.

    \b
    Example:
        flama get --source huggingface --family ml philschmid/tiny-bert-sst2-distilled
        flama get --source huggingface --family llm Qwen/Qwen2.5-0.5B
    """
    output_path = pathlib.Path(output or f"{model_name.replace('/', '_')}.flm")

    if source == "huggingface":
        downloader: _Downloader = _HuggingFaceDownloader(model_name, output_path, family, max_concurrent=max_concurrent)
    else:  # pragma: no cover -- click.Choice already rejects unknown sources
        raise click.BadParameter(f"Unknown source: {source}", param_hint="--source")

    asyncio.run(downloader.run())


get = command
