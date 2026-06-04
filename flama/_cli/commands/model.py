import abc
import asyncio
import functools
import importlib
import json
import typing as t

import click

from flama import types
from flama._cli.config.app import _parse_params
from flama._cli.formatting import CONSOLE, FlamaCommand, FlamaGroup
from flama._core.json_encoder import encode_json
from flama.models import ModelComponentBuilder
from flama.models.base import BaseModel, LLMModel, MLModel
from flama.models.engine.llm.decoder.decoder import Decoder
from flama.models.transport.output.llm.event import TextEvent
from flama.models.wire.dialect.llm.openai.dialect import OpenAIDialect

if t.TYPE_CHECKING:
    from flama.models import ModelComponent
    from flama.models.transport.output.llm.event import Event

__all__ = ["model", "command"]


_TRANSPORT_CHOICES: tuple[types.LLMTransportShape, ...] = t.get_args(types.LLMTransportShape)
_CHANNEL_SCANNER_CHOICES: tuple[str, ...] = (*t.get_args(types.LLMEngineChannelScanners), "auto")
_TOOL_SCANNER_CHOICES: tuple[str, ...] = (*t.get_args(types.LLMEngineToolScanners), "auto")
_TOOL_PARSER_CHOICES: tuple[str, ...] = (*t.get_args(types.LLMEngineToolParsers), "auto")
_CHANNEL_WILDCARDS: t.Final[frozenset[str]] = frozenset({"all", "*"})


class _DecoderRef(click.ParamType):
    """Parameter type for ``--channel-scanner`` / ``--tool-scanner`` / ``--tool-parser``.

    Accepts a registry name (one of *choices*, including ``"passthrough"``), the special
    token ``auto``, or a ``pkg.module:Object`` path that resolves to a pre-built scanner /
    parser instance via :mod:`importlib`. Resolution happens at parse time so failures
    surface immediately; instance-level type validation is deferred to
    :class:`~flama.models.Decoder`.
    """

    name = "decoder_ref"

    def __init__(self, choices: tuple[str, ...]) -> None:
        self._choices = choices

    def convert(self, value: t.Any, param: click.Parameter | None, ctx: click.Context | None) -> t.Any:
        if not isinstance(value, str):
            return value
        if value in self._choices:
            return value
        if ":" not in value:
            self.fail(
                f"Unknown value {value!r}; expected one of {sorted(self._choices)} or 'pkg.module:Object'",
                param,
                ctx,
            )
        module_path, _, attr = value.partition(":")
        try:
            return getattr(importlib.import_module(module_path), attr)
        except (ImportError, AttributeError) as exc:
            self.fail(f"Cannot resolve {value!r}: {exc}", param, ctx)


def _resolve_cli_value(value: t.Any) -> t.Any:
    """Map CLI tokens to the values :class:`Decoder` consumes natively.

    ``"auto"`` is translated to :data:`None` (defer to engine detection); everything else
    (registry names including ``"passthrough"``, and import-path-resolved instances) is
    passed through verbatim.
    """
    return None if value == "auto" else value


class _Args(t.TypedDict):
    """Common base for parsed CLI args.

    Has no required keys; concrete families extend it with their own fields. The base class
    abstracts use this type so subclass returns are covariantly compatible.
    """


class _MLArgs(_Args):
    """Parsed CLI args bag for :class:`_ML`."""


class _LLMArgs(_Args):
    """Parsed CLI args bag for :class:`_LLM`.

    *model_kwargs* are spread into :meth:`LLMModel.query` / :meth:`LLMModel.stream`. *channels*
    is the resolved channel filter: ``None`` for the wildcard (every channel passes) or the
    set of channel names that should pass the filter.
    """

    model_kwargs: dict[str, t.Any]
    channels: frozenset[str] | None


M = t.TypeVar("M", bound=BaseModel)
A = t.TypeVar("A", bound=_Args)


@click.group(name="model", cls=FlamaGroup)
@click.argument("flama-model-path", envvar="FLAMA_MODEL_PATH")
@click.option(
    "--channel-scanner",
    "channel_scanner",
    type=_DecoderRef(_CHANNEL_SCANNER_CHOICES),
    default="auto",
    help="Channel scanner format (LLM-only). One of "
    f"{sorted(_CHANNEL_SCANNER_CHOICES)} or a 'pkg.module:Object' import path resolving to a "
    "pre-built scanner. 'auto' (default) defers to preflight detection; 'passthrough' "
    "disables channel splitting entirely.",
)
@click.option(
    "--tool-scanner",
    "tool_scanner",
    type=_DecoderRef(_TOOL_SCANNER_CHOICES),
    default="auto",
    help="Tool scanner format (LLM-only). One of "
    f"{sorted(_TOOL_SCANNER_CHOICES)} or a 'pkg.module:Object' import path resolving to a "
    "pre-built scanner. 'auto' (default) defers to chat-template introspection; 'passthrough' "
    "disables tool extraction entirely.",
)
@click.option(
    "--tool-parser",
    "tool_parser",
    type=_DecoderRef(_TOOL_PARSER_CHOICES),
    default="auto",
    help="Tool body parser (LLM-only). One of "
    f"{sorted(_TOOL_PARSER_CHOICES)} or a 'pkg.module:Object' import path resolving to a "
    "ToolParser. 'auto' (default) defers to chat-template introspection; 'passthrough' "
    "surfaces tool bodies as raw bytes via the passthrough parser.",
)
@click.pass_context
def command(
    ctx: click.Context,
    flama_model_path: str,
    channel_scanner: t.Any,
    tool_scanner: t.Any,
    tool_parser: t.Any,
) -> None:
    """Interact with a packaged model without server.

    Works with both traditional ML models and large language models. The artifact family is recorded in the .flm
    manifest at download time (``flama get --family ...``) and dispatched accordingly. LLM artifacts
    automatically pick the available runtime - vLLM on Linux/CUDA, MLX on macOS / Apple Silicon -
    based on what is importable in the current environment. To serve models over HTTP, use 'flama serve'.

    <FLAMA_MODEL_PATH> is the path of the model to be used, e.g. 'path/to/model.flm'. This can be passed
    directly as argument of the command line, or by environment variable.

    --channel-scanner, --tool-scanner and --tool-parser are LLM-only; they are rejected for ML
    artifacts at build time.
    """
    from flama.serialize.serializer import Serializer

    try:
        family = Serializer.meta(path=flama_model_path).framework.family
    except FileNotFoundError:
        raise click.BadParameter("Model file not found.")

    decoder = (
        Decoder(
            _resolve_cli_value(channel_scanner),
            _resolve_cli_value(tool_scanner),
            _resolve_cli_value(tool_parser),
        )
        if family == "llm"
        else None
    )
    ctx.obj = ModelComponentBuilder.build(flama_model_path, decoder=decoder, autoload=True)


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
    "input_file",
    type=click.File("r"),
    default="-",
    help="Input file to read from (defaults to stdin). For ML models, a JSON list of feature vectors; "
    "for LLMs, a prompt or (with --transport conversation) a JSON list of messages.",
)
@click.option(
    "--transport",
    type=click.Choice(_TRANSPORT_CHOICES),
    default=None,
    help="LLM input shape (raw|chat|conversation). Defaults to the model's default transport.",
)
@click.option(
    "--system",
    "system_text",
    type=str,
    default=None,
    help="LLM system instruction (chat transport only).",
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
@click.option(
    "--channel",
    "channels",
    multiple=True,
    default=(),
    help="Channel(s) to include in output (LLM only, repeatable). Use 'all' or '*' for every "
    "channel. Defaults to the 'output' channel only. With one channel the output is plain text; "
    "with several or 'all' the output is a JSON list of {channel, text} blocks.",
)
@click.pass_obj
def run(
    model: "ModelComponent",
    input_file: t.IO[str],
    transport: types.LLMTransportShape | None,
    system_text: str | None,
    param: tuple[str, ...],
    output_file: t.IO[str],
    pretty: bool,
    channels: tuple[str, ...],
) -> None:
    """Run a one-shot inference.

    For ML models, the input must be a JSON list of feature vectors and the output is a JSON list of
    predictions. For LLM models, the input is a prompt and the output is the generated response.

    \b
    Examples:
        echo '[[0, 0], [1, 1]]' | flama model model.flm run
        flama model model.flm run -i input.json
        echo "What is Python?" | flama model llm.flm run
        echo "What is Python?" | flama model llm.flm run --system "Be concise."
        flama model llm.flm run --transport conversation -i conv.json
        echo "Explain AI" | flama model llm.flm run --param temperature=0.7 --param max_tokens=100
        echo "Explain AI" | flama model llm.flm run --channel all
        echo "Explain AI" | flama model llm.flm run --channel thinking --channel output
    """
    dump = functools.partial(encode_json, sort_keys=True, indent=4) if pretty else encode_json
    _Cli.build(model).run(
        input_file.read(),
        transport=transport,
        system=system_text,
        param=param,
        output_file=output_file,
        dump=dump,
        channels=channels,
    )


@command.command(name="stream", cls=FlamaCommand, context_settings={"auto_envvar_prefix": "FLAMA"})
@click.option(
    "-i",
    "--input",
    "input_file",
    type=click.File("r"),
    default="-",
    help="Input file to read from (defaults to stdin). For ML models, a JSON list of feature vectors; "
    "for LLMs, a prompt or (with --transport conversation) a JSON list of messages.",
)
@click.option(
    "--transport",
    type=click.Choice(_TRANSPORT_CHOICES),
    default=None,
    help="LLM input shape (raw|chat|conversation). Defaults to the model's default transport.",
)
@click.option(
    "--system",
    "system_text",
    type=str,
    default=None,
    help="LLM system instruction (chat transport only).",
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
@click.option(
    "--channel",
    "channels",
    multiple=True,
    default=(),
    help="Channel(s) to include in output (LLM only, repeatable). Use 'all' or '*' for every "
    "channel. Defaults to the 'output' channel only. With one channel the output is raw text "
    "deltas; with several or 'all' each chunk is prefixed with '[channel] '.",
)
@click.pass_obj
def stream(
    model: "ModelComponent",
    input_file: t.IO[str],
    transport: types.LLMTransportShape | None,
    system_text: str | None,
    param: tuple[str, ...],
    output_file: t.IO[str],
    buffered: bool,
    channels: tuple[str, ...],
) -> None:
    """Stream output from a model.

    For ML models, the input must be a JSON list of feature vectors and the model emits one output per
    item. For LLM models, the input is a prompt and the model emits one block at a time.

    \b
    Examples:
        echo '[[0, 0], [1, 1]]' | flama model model.flm stream
        flama model model.flm stream -i input.json --buffer
        echo "What is Python?" | flama model llm.flm stream
        echo "What is Python?" | flama model llm.flm stream --system "Be concise."
        flama model llm.flm stream --transport conversation -i conv.json
        echo "Explain AI" | flama model llm.flm stream --param temperature=0.7
        echo "Solve 2+2" | flama model llm.flm stream --channel all
    """
    _Cli.build(model).stream(
        input_file.read(),
        transport=transport,
        system=system_text,
        param=param,
        output_file=output_file,
        buffered=buffered,
        channels=channels,
    )


class _Cli(abc.ABC, t.Generic[M, A]):
    """Base CLI runner for a model family.

    One concrete subclass per family (:class:`_LLM`, :class:`_ML`); :meth:`build` dispatches to
    the right one based on the component's model class. The base class owns the shared
    pipeline — argument validation, input decoding, asyncio bridging, and output I/O — while
    subclasses implement only the family-specific contract: how CLI options are validated and
    translated into model kwargs (:meth:`_parse_args`), how the raw input text is decoded
    (:meth:`_parse_input`), and how the model is invoked for one-shot or streaming output
    (:meth:`_run_output`, :meth:`_stream_iterator`).
    """

    def __init__(self, model: M, /) -> None:
        self.model = model

    @classmethod
    def build(cls, component: "ModelComponent", /) -> "_Cli":
        """Dispatch to the right runner for *component*'s model type.

        :param component: The injected :class:`~flama.models.ModelComponent`.
        :return: An instantiated runner whose :attr:`model` is narrowed to the matching family.
        :raises click.UsageError: If the model is neither :class:`LLMModel` nor :class:`MLModel`.
        """
        if isinstance(component.model, LLMModel):
            return _LLM(component.model)
        if isinstance(component.model, MLModel):
            return _ML(component.model)
        raise click.UsageError("Unsupported model type.")

    def run(
        self,
        raw: str,
        *,
        transport: types.LLMTransportShape | None,
        system: str | None,
        param: tuple[str, ...],
        output_file: t.IO[str],
        dump: t.Callable[..., bytes],
        channels: tuple[str, ...],
    ) -> None:
        """Run a one-shot inference and write the formatted result to *output_file*.

        Subclasses implement :meth:`_parse_args`, :meth:`_parse_input`, and :meth:`_run_output`.
        :meth:`BaseModel.startup` is awaited up front so the artifact is materialised and any
        family-specific setup (decoder detection on LLMs) runs before invocation.
        """
        args = self._parse_args(transport=transport, system=system, param=param, channels=channels)
        payload = self._parse_input(raw, args)

        async def _do_run() -> str:
            await self.model.startup()
            return await self._run_output(payload, args, dump=dump)

        click.echo(asyncio.run(_do_run()), file=output_file)

    def stream(
        self,
        raw: str,
        *,
        transport: types.LLMTransportShape | None,
        system: str | None,
        param: tuple[str, ...],
        output_file: t.IO[str],
        buffered: bool,
        channels: tuple[str, ...],
    ) -> None:
        """Stream inference output to *output_file*, optionally buffering until completion.

        Subclasses implement :meth:`_parse_args`, :meth:`_parse_input`, and
        :meth:`_stream_iterator`. :meth:`BaseModel.startup` is awaited up front so the artifact
        is materialised and any family-specific setup (decoder detection on LLMs) runs before
        the first chunk is produced. With ``buffered=True`` all chunks are joined and written
        once. Otherwise each chunk is written verbatim (no trailing newline) and a final
        newline is appended when *output_file* is a real file so terminal output stays clean.
        """
        args = self._parse_args(transport=transport, system=system, param=param, channels=channels)
        payload = self._parse_input(raw, args)

        async def _drain() -> None:
            await self.model.startup()
            emitter = self._stream_iterator(payload, args)
            if buffered:
                click.echo("".join([chunk async for chunk in emitter]), file=output_file)
                return
            async for chunk in emitter:
                click.echo(chunk, file=output_file, nl=False)
            if output_file.name != "<stdout>":
                click.echo("", file=output_file)

        asyncio.run(_drain())

    @abc.abstractmethod
    def _parse_args(
        self,
        *,
        transport: types.LLMTransportShape | None,
        system: str | None,
        param: tuple[str, ...],
        channels: tuple[str, ...],
    ) -> A:
        """Validate CLI options and produce a parsed-args bag.

        All option-level validation lives here, including family-specific rejections (e.g.
        ``--param`` on ML models). The returned :class:`_Args` (a :class:`typing.TypedDict`)
        is threaded as ``args`` to :meth:`_parse_input`, :meth:`_run_output`, and
        :meth:`_stream_iterator`; each family extends :class:`_Args` with its own shape (e.g.
        :class:`_LLMArgs`).
        """
        ...

    @abc.abstractmethod
    def _parse_input(self, raw: str, args: A) -> t.Any:
        """Decode *raw* into the family's expected input payload.

        Receives *args* from :meth:`_parse_args` so families can vary their parsing on
        upstream decisions (e.g. LLM ``conversation`` transport parses *raw* as a JSON list
        of messages).
        """
        ...

    @abc.abstractmethod
    async def _run_output(self, payload: t.Any, args: A, *, dump: t.Callable[..., bytes]) -> str:
        """Execute a one-shot inference and return the formatted output string."""
        ...

    @abc.abstractmethod
    def _stream_iterator(self, payload: t.Any, args: A) -> t.AsyncIterator[str]:
        """Yield formatted text chunks for the family's streaming output.

        Concrete implementations are typically ``async def`` with ``yield`` (async generators).
        """
        ...


class _LLM(_Cli[LLMModel, _LLMArgs]):
    """CLI runner for :class:`LLMModel`."""

    def _parse_args(
        self,
        *,
        transport: types.LLMTransportShape | None,
        system: str | None,
        param: tuple[str, ...],
        channels: tuple[str, ...],
    ) -> _LLMArgs:
        """Validate transport/system combos and produce a typed :class:`_LLMArgs` bag.

        Defaults to :attr:`LLMModel.default_transport` when *transport* is not given.
        ``--system`` is only valid for ``chat``. Channels are resolved inline: empty input
        keeps only the ``"output"`` channel; ``all`` / ``*`` collapse to ``None`` (wildcard).

        :raises click.UsageError: For invalid transport/system combinations.
        :raises click.BadParameter: For malformed ``--param`` entries.
        """
        params = self._parse_params(param)

        if not channels:
            resolved_channels = frozenset({"output"})
        elif _CHANNEL_WILDCARDS & set(channels):
            resolved_channels = None
        else:
            resolved_channels = frozenset(channels)

        resolved = transport or self.model.default_transport
        if resolved == "raw":
            if system is not None:
                raise click.UsageError("--system is only valid for transport='chat'.")
            return _LLMArgs(model_kwargs={"transport": "raw", **params}, channels=resolved_channels)
        if resolved == "chat":
            return _LLMArgs(model_kwargs={"system": system, "transport": "chat", **params}, channels=resolved_channels)
        if system is not None:
            raise click.UsageError("--system is only valid for transport='chat'.")
        return _LLMArgs(model_kwargs={"transport": "conversation", **params}, channels=resolved_channels)

    @staticmethod
    def _parse_params(param: tuple[str, ...]) -> dict[str, t.Any]:
        """Parse ``--param key=value`` tuples into a dict.

        Thin wrapper around :func:`flama._cli.config.app._parse_params` that translates
        :class:`ValueError` into :class:`click.BadParameter` so malformed entries surface as
        a CLI usage error rather than an uncaught exception.

        :raises click.BadParameter: When an entry is missing the ``=`` separator.
        """
        try:
            return _parse_params(param)
        except ValueError as exc:
            raise click.BadParameter(str(exc), param_hint="--param")

    def _parse_input(self, raw: str, args: _LLMArgs) -> t.Any:
        """Return the prompt string (raw/chat) or parse a JSON list of messages (conversation)."""
        if args["model_kwargs"].get("transport") != "conversation":
            return raw
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as e:
            raise click.UsageError(f"Conversation input must be valid JSON: {e}")
        if not isinstance(decoded, list) or not decoded:
            raise click.UsageError("Conversation input must be a non-empty JSON list of messages.")
        for i, item in enumerate(decoded):
            if not isinstance(item, dict):
                raise click.UsageError(f"messages[{i}] must be an object with 'role' and 'content' fields.")
        try:
            return OpenAIDialect.parse(t.cast(list[dict[str, t.Any]], decoded), kind="messages")
        except ValueError as e:
            raise click.UsageError(f"messages: {e}")

    async def _run_output(self, payload: t.Any, args: _LLMArgs, *, dump: t.Callable[..., bytes]) -> str:
        """Filter blocks by *args["channels"]* and format the joined output.

        With a single channel the matching blocks' text is concatenated as plain text. With the wildcard
        (``channels is None``) or two-plus channels the result is a JSON list of ``{channel, text}`` objects so
        callers can disambiguate per-block origin. Lifecycle markers and usage metadata are dropped at this
        layer — only the :class:`TextEvent` portion of the decoder's output is rendered.
        """
        channels = args["channels"]
        blocks = await self._query(payload, **args["model_kwargs"])
        text_blocks = [b for b in blocks if isinstance(b, TextEvent)]
        filtered = [b for b in text_blocks if channels is None or b.channel in channels]
        if channels is None or len(channels) > 1:
            return dump([{"channel": b.channel, "text": b.text} for b in filtered]).decode("utf-8")
        return "".join(b.text for b in filtered)

    async def _stream_iterator(self, payload: t.Any, args: _LLMArgs) -> t.AsyncIterator[str]:
        """Yield text chunks from :meth:`LLMModel.stream`, filtered by *args["channels"]*.

        With a single channel selected the matching blocks' text is emitted verbatim so the
        terminal reads as plain prose. When the wildcard (``channels is None``) or several
        channels are selected each chunk is prefixed with ``[channel] `` (a leading newline
        separates channel switches) so the multi-channel output stays readable as it streams.
        :class:`~flama.models.engine.llm.decoder.TraceEvent` events from the underlying model are dropped
        — the CLI is consumer-side rendering, not transport-level metadata.
        """
        channels = args["channels"]
        multi = channels is None or len(channels) > 1
        last_channel: str | None = None
        async for item in await self._stream(payload, **args["model_kwargs"]):
            if not isinstance(item, TextEvent):
                continue
            if not (channels is None or item.channel in channels):
                continue
            if not multi:
                yield item.text
                continue
            if item.channel != last_channel:
                yield f"[{item.channel}] " if last_channel is None else f"\n[{item.channel}] "
                last_channel = item.channel
            yield item.text

    def _query(self, payload: t.Any, **kwargs: t.Any) -> t.Awaitable[t.Sequence["Event"]]:
        if kwargs.get("transport") == "conversation":
            return self.model.query(None, messages=payload, **kwargs)
        return self.model.query(payload, **kwargs)

    async def _stream(self, payload: t.Any, **kwargs: t.Any) -> "t.AsyncIterator[Event]":
        if kwargs.get("transport") == "conversation":
            return await self.model.stream(None, messages=payload, **kwargs)
        return await self.model.stream(payload, **kwargs)


class _ML(_Cli[MLModel, _MLArgs]):
    """CLI runner for :class:`MLModel`."""

    def _parse_args(
        self,
        *,
        transport: types.LLMTransportShape | None,
        system: str | None,
        param: tuple[str, ...],
        channels: tuple[str, ...],
    ) -> _MLArgs:
        """Reject LLM-only options. ML models accept no extra CLI knobs."""
        if param:
            raise click.UsageError("--param is not supported for ML models.")
        if transport is not None:
            raise click.UsageError("--transport is not supported for ML models.")
        if system is not None:
            raise click.UsageError("--system is not supported for ML models.")
        if channels:
            raise click.UsageError("--channel is only valid for LLM models.")
        return _MLArgs()

    def _parse_input(self, raw: str, args: _MLArgs) -> t.Any:
        """Decode *raw* as a JSON document (typically a list of feature vectors)."""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise click.BadParameter("Input must be valid JSON for ML models.")

    async def _run_output(self, payload: t.Any, args: _MLArgs, *, dump: t.Callable[..., bytes]) -> str:
        return dump(self.model.predict(payload)).decode("utf-8")

    async def _stream_iterator(self, payload: t.Any, args: _MLArgs) -> t.AsyncIterator[str]:
        """Yield JSON-encoded predictions from :meth:`MLModel.stream`."""
        async for item in self.model.stream(payload):
            yield encode_json(item, compact=True).decode()


model = command.callback
