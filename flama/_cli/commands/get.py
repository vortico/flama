import abc
import asyncio
import dataclasses
import os
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

from flama import concurrency, types
from flama._cli.formatting import CONSOLE, FlamaCommand
from flama.client import Client
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


class _Downloader(abc.ABC):
    """Download a model from a remote source and package it into a ``.flm`` artifact.

    Subclasses encapsulate source-specific logic (auth, listing, transfer) by overriding
    :attr:`_lib` and :meth:`_download`. The orchestration (temp dir lifecycle, async
    runner and final ``Serializer.dump`` packaging) is shared on the base class.

    :param model_name: Source-specific model identifier.
    :param output: Destination ``.flm`` path.
    """

    _lib: t.ClassVar[types.Lib]

    def __init__(self, model_name: str, output: pathlib.Path) -> None:
        self.model_name = model_name
        self.output = output
        self.config: dict[str, str] = {}
        self.extra: dict[str, str] = {"model_name": self.model_name}
        self.tmp = tempfile.TemporaryDirectory()

    async def run(self) -> None:
        """Download to a temporary directory and package the result as ``.flm``."""
        async with self:
            await self._download()
            self._pack()

        CONSOLE.print(f"Model saved to [bold]{self.output}[/bold]")

    @abc.abstractmethod
    async def _download(self) -> None:
        """Download model files into ``self.tmp.name`` and populate ``self.config`` / ``self.extra``."""
        ...

    def _pack(self) -> None:
        with CONSOLE.status("Packaging..."):
            Serializer.dump(self.tmp.name, path=self.output, lib=self._lib, config=self.config, extra=self.extra)

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
    _lib: t.ClassVar[types.MLLib] = "transformers"

    def __init__(self, model_name: str, output: pathlib.Path, *, max_concurrent: int) -> None:
        super().__init__(model_name, output)
        self.client = Client(base_url=self.BASE_URL, follow_redirects=True, http2=True)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.retry = _RetryPolicy()

    async def _download(self) -> None:
        response = await self.client.get(f"/api/models/{self.model_name}", params={"blobs": "true"})
        response.raise_for_status()
        info = response.json()

        self.config["task"] = info.get("pipeline_tag")

        siblings = info.get("siblings", [])
        files = [s["rfilename"] for s in siblings]
        total_size = sum(s.get("size", 0) for s in siblings)

        with Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=CONSOLE,
        ) as progress:
            progress_id = progress.add_task("Downloading", total=total_size)

            tasks = await concurrency.run_task_group(
                *(self._download_file(name, progress, progress_id) for name in files)
            )
            for task in tasks:
                task.result()

    async def _download_file(self, filename: str, progress: Progress, progress_id: TaskID) -> None:
        async with self.semaphore:
            dest = pathlib.Path(self.tmp.name) / filename
            await concurrency.run(dest.parent.mkdir, parents=True, exist_ok=True)
            await self.retry(lambda: self._stream_to_file(filename, dest, progress, progress_id))

    async def _stream_to_file(self, filename: str, dest: pathlib.Path, progress: Progress, progress_id: TaskID) -> None:
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        written = 0
        try:
            async with self.client.stream("GET", f"/{self.model_name}/resolve/main/{filename}") as stream:
                stream.raise_for_status()
                f = t.cast(t.BinaryIO, await concurrency.run(tmp.open, "wb"))
                try:
                    async for chunk in stream.aiter_bytes(chunk_size=60 * 2**10):
                        await concurrency.run(f.write, chunk)
                        written += len(chunk)
                        progress.update(progress_id, advance=len(chunk))
                finally:
                    await concurrency.run(f.close)
            await concurrency.run(os.replace, tmp, dest)
        except BaseException:
            if written:
                progress.update(progress_id, advance=-written)
            await concurrency.run(tmp.unlink, missing_ok=True)
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
@click.option("-o", "--output", default=None, help="Output .flm path (default: <model-name>.flm).")
@click.option(
    "--max-concurrent",
    type=click.IntRange(min=1),
    default=8,
    show_default=True,
    help="Maximum number of files to download concurrently.",
)
def command(model_name: str, source: str, output: str | None, max_concurrent: int) -> None:
    """Download and package a model as .flm.

    Download a model from a supported source and serialize it into Flama's .flm format, ready for serving with
    'flama llm <path> run'.

    \b
    Example:
        flama get --source huggingface Qwen/Qwen2.5-0.5B
    """
    output_path = pathlib.Path(output or f"{model_name.replace('/', '_')}.flm")

    if source == "huggingface":
        downloader: _Downloader = _HuggingFaceDownloader(model_name, output_path, max_concurrent=max_concurrent)
    else:  # pragma: no cover -- click.Choice already rejects unknown sources
        raise click.BadParameter(f"Unknown source: {source}", param_hint="--source")

    asyncio.run(downloader.run())


get = command
