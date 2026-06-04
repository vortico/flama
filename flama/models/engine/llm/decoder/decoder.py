import dataclasses
import typing as t

from flama import types
from flama.models.engine.llm.decoder.markers import MarkerScanner, PassthroughScanner, Scanner
from flama.models.engine.llm.decoder.parsers import (
    CallNotationParser,
    JSONArrayParser,
    JSONNamedSequenceParser,
    JSONObjectParser,
    JSONSequenceParser,
    PassthroughParser,
    PythonicParser,
    ToolParser,
)

__all__ = ["ChannelPolicy", "Decoder"]

TEMPLATE_BODY_MAX_CHARS: t.Final[int] = 1024


_KNOWN_CHANNEL_SCANNERS: t.Final[dict[types.LLMEngineChannelScanners, Scanner]] = {
    "passthrough": PassthroughScanner(),
    "harmony": MarkerScanner(name="harmony", start="<|channel|>", end="<|end|>", inner=r"\w+", separator="<|message|>"),
    "channel": MarkerScanner(name="channel", start="<|channel>", end="<channel|>", inner=r"\w+", separator="\n"),
    "think": MarkerScanner(name="think", start="<think>", end="</think>"),
}

_KNOWN_TOOL_SCANNERS: t.Final[dict[types.LLMEngineToolScanners, Scanner]] = {
    "passthrough": PassthroughScanner(),
    "tool_call": MarkerScanner(name="tool_call", start="<tool_call>", end="</tool_call>"),
    "tool_calls": MarkerScanner(name="tool_calls", start="[TOOL_CALLS]", end=None),
    "python_tag": MarkerScanner(name="python_tag", start="<|python_tag|>", end=None),
    "pythonic": MarkerScanner(name="pythonic", start="[", end="]", start_of_buffer_only=True),
    "python_block": MarkerScanner(name="python_block", start="<|python_start|>", end="<|python_end|>"),
    "tool_call_pipe": MarkerScanner(name="tool_call_pipe", start="<|tool_call>", end="<tool_call|>"),
}


_KNOWN_TOOL_PARSERS: t.Final[dict[types.LLMEngineToolParsers, ToolParser]] = {
    "passthrough": PassthroughParser(),
    "json_object": JSONObjectParser(name="json_object", args_fields=("arguments",)),
    "json_array": JSONArrayParser(name="json_array", args_fields=("arguments",)),
    "json_sequence": JSONSequenceParser(name="json_sequence", separator="; "),
    "named_json_sequence": JSONNamedSequenceParser(name="named_json_sequence"),
    "pythonic": PythonicParser(name="pythonic"),
    "call_notation": CallNotationParser(name="call_notation"),
}


@dataclasses.dataclass(frozen=True)
class ChannelPolicy:
    """Immutable channel-naming policy attached to a :class:`Decoder`.

    Defaults live as class attributes so :class:`Decoder` can reference them in its public
    signature without restating the literal values. The owning :class:`_FSM` reads
    :attr:`output` for content outside any channel and routes captured channel names through
    :meth:`resolve` for in-channel content.

    :param output: Channel name for content outside any marker pair (also used in passthrough
        and as the fallback when flushing an unclosed buffer at EOF).
    :param overrides: Optional rewrite mapping applied to captured channel names only;
        ``output`` is *not* subject to it.
    """

    DEFAULT_OUTPUT: t.ClassVar[str] = "output"

    output: str = DEFAULT_OUTPUT
    overrides: t.Mapping[str, str] | None = None

    def resolve(self, captured: str | None) -> str | None:
        """Resolve a captured channel name to its canonical form, or :data:`None` when unnamed.

        Markers whose ``inner`` group captured nothing (e.g. ``<think>...</think>``) carry no
        identity, so they round-trip as :data:`None` and let downstream consumers (clients,
        renderers) decide how to label them - rather than forcing every model into a
        ``"thinking"`` synonym the project happened to pick. ``overrides`` only rewrites named
        captures; an unnamed capture stays :data:`None` regardless of the override map.
        """
        if not captured:
            return None

        return self.overrides.get(captured, captured) if self.overrides else captured


@dataclasses.dataclass(frozen=True)
class _ResolvedDecoder:
    channel_scanner: Scanner
    tool_scanner: Scanner
    tool_parser: ToolParser
    policy: ChannelPolicy


@dataclasses.dataclass(frozen=True)
class Decoder:
    """Decoder configuration: channel + tool scanners, tool body parser, and channel policy.

    Construction is polymorphic on each slot argument:

    *   :data:`None` (default) - auto-detect at warmup / model load.
    *   :data:`~flama.types.LLMEngineChannelScanners` / :data:`~flama.types.LLMEngineToolScanners` /
        :data:`~flama.types.LLMEngineToolParsers` - registry lookup against the matching
        :data:`_KNOWN_CHANNEL_SCANNERS` / :data:`_KNOWN_TOOL_SCANNERS` /
        :data:`_KNOWN_TOOL_PARSERS` registry. The string ``"passthrough"`` is the explicit
        "no scanner / no parser" choice.
    *   :class:`Scanner` / :class:`ToolParser` instance - used verbatim. Parsers are stateless
        and shareable, so the same instance covers any number of streams.

    :data:`None` field values express "this slot should be auto-detected at warmup". Each
    independent slot can mix-and-match: ``Decoder("think")`` keeps Think for the channel and
    auto-detects tools and parser; ``Decoder("think", "tool_call", "json_object")`` is fully
    explicit and skips detection entirely.

    Detection lives on the class so a fully-resolved decoder can be built from raw text samples without an
    engine: :meth:`resolve` (passthrough-fallback) and :meth:`_try_resolve` (strict, returns :data:`None` on
    partial detection) aggregate the three slot-specific detectors (:meth:`_detect_channel_scanner`,
    :meth:`_detect_tool_scanner`, :meth:`_detect_tool_parser`). :class:`LLMCodec` reuses the same helpers to
    support stepped detection at warmup (cheap template-only pass first, full template + preflight as fallback).

    Instances are logically immutable; use :func:`dataclasses.replace` to derive variants.

    :param channel_scanner: Channel scanner selector or pre-resolved instance, or :data:`None`
        to auto-detect.
    :param tool_scanner: Tool scanner selector or pre-resolved instance, or :data:`None` to
        auto-detect.
    :param tool_parser: Tool body parser selector or instance, or :data:`None` to auto-detect.
    :param policy: Channel-naming policy. Defaults to a fresh :class:`ChannelPolicy` with
        ``output="output"`` / ``thought="thinking"`` and no overrides.
    :raises KeyError: If a string selector is not a registry key.
    """

    channel_scanner: Scanner | types.LLMEngineChannelScanners | None = None
    tool_scanner: Scanner | types.LLMEngineToolScanners | None = None
    tool_parser: ToolParser | types.LLMEngineToolParsers | None = None
    policy: ChannelPolicy = dataclasses.field(default_factory=ChannelPolicy)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "channel_scanner",
            (
                self.channel_scanner
                if self.channel_scanner is None or isinstance(self.channel_scanner, Scanner)
                else _KNOWN_CHANNEL_SCANNERS[self.channel_scanner]
            ),
        )
        object.__setattr__(
            self,
            "tool_scanner",
            (
                self.tool_scanner
                if self.tool_scanner is None or isinstance(self.tool_scanner, Scanner)
                else _KNOWN_TOOL_SCANNERS[self.tool_scanner]
            ),
        )
        object.__setattr__(
            self,
            "tool_parser",
            (
                self.tool_parser
                if self.tool_parser is None or isinstance(self.tool_parser, ToolParser)
                else _KNOWN_TOOL_PARSERS[self.tool_parser]
            ),
        )

    @property
    def is_resolved(self) -> bool:
        """True when every slot is already a concrete instance (no detection required)."""
        return self.channel_scanner is not None and self.tool_scanner is not None and self.tool_parser is not None

    @t.overload
    def resolve(self, *samples: str, default: t.Literal[True] = True) -> _ResolvedDecoder: ...
    @t.overload
    def resolve(self, *samples: str, default: t.Literal[False]) -> _ResolvedDecoder | None: ...
    def resolve(self, *samples: str, default: bool = True) -> _ResolvedDecoder | None:
        """Build a fully-resolved decoder from *samples*, falling back to passthrough sentinels for undetected slots.

        Calls :meth:`_detect_channel_scanner`, :meth:`_detect_tool_scanner`, and :meth:`_detect_tool_parser` in
        turn, feeding the freshly-detected tool scanner into the parser detector (via :func:`dataclasses.replace`)
        so the parser is probed against the right marker body. Samples are consumed in the order given (typically
        chat-template sample first, preflight sample second); each detector returns the first match across all
        samples or :data:`None`, in which case the corresponding passthrough sentinel substitutes.

        :param samples: Text snippets to probe (chat-template sample, preflight output, ...).
        :return: A :class:`_ResolvedDecoder` with every slot resolved (never :data:`None`).
        """
        if (channel_scanner := self._detect_channel_scanner(*samples)) is None:
            if not default:
                return None
            channel_scanner = PassthroughScanner()
        if (tool_scanner := self._detect_tool_scanner(*samples)) is None:
            if not default:
                return None
            tool_scanner = PassthroughScanner()
        if (tool_parser := self._detect_tool_parser(*samples, scanner=tool_scanner)) is None:
            if not default:
                return None
            tool_parser = PassthroughParser()
        return _ResolvedDecoder(channel_scanner, tool_scanner, tool_parser, self.policy)

    def _detect_channel_scanner(self, *samples: str) -> Scanner | None:
        """First :data:`_KNOWN_CHANNEL_SCANNERS` entry that matches any of *samples*.

        Returns :attr:`channel_scanner` verbatim when it was pre-pinned to a :class:`Scanner` instance.
        Samples are scanned in order; empty samples are skipped. Returns :data:`None` if no scanner recognises any
        sample (or no samples are given); callers decide whether to substitute :class:`PassthroughScanner`.
        """
        if isinstance(self.channel_scanner, Scanner):
            return self.channel_scanner

        for sample in samples:
            if not sample:
                continue
            for scanner in _KNOWN_CHANNEL_SCANNERS.values():
                if scanner.detect(sample):
                    return scanner

        return None

    def _detect_tool_scanner(self, *samples: str) -> Scanner | None:
        """First :data:`_KNOWN_TOOL_SCANNERS` entry that matches any of *samples*.

        Returns :attr:`tool_scanner` verbatim when it was pre-pinned to a :class:`Scanner` instance.
        Samples are scanned in order; empty samples are skipped. Returns :data:`None` if no scanner recognises any
        sample (or no samples are given); callers decide whether to substitute :class:`PassthroughScanner`.
        """
        if isinstance(self.tool_scanner, Scanner):
            return self.tool_scanner

        for sample in samples:
            if not sample:
                continue
            for scanner in _KNOWN_TOOL_SCANNERS.values():
                if scanner.detect(sample):
                    return scanner

        return None

    def _detect_tool_parser(self, *samples: str, scanner: Scanner) -> ToolParser | None:
        """First :data:`_KNOWN_TOOL_PARSERS` entry that recognises any body inside :attr:`tool_scanner`'s markers.

        Returns :attr:`tool_parser` verbatim when it was pre-pinned to a :class:`ToolParser` instance.
        Otherwise, iterates over every well-formed marker pair across *samples* (see :meth:`_iter_marker_bodies`)
        and probes every known parser via :meth:`ToolParser.detect`; the first match wins. Iterating instead of
        slicing the first occurrence is required because some chat templates (Qwen2.5, Qwen2.5-Coder, ...) emit
        an instructional ``<tool_call>...</tool_call>`` example in the system prompt with literal placeholders
        before the real synthetic assistant turn; the placeholder body never parses as JSON and would otherwise
        force a passthrough fallback. Returns :data:`None` when :attr:`tool_scanner` is not a :class:`MarkerScanner`
        or no sample produces a recognisable body.
        """
        if isinstance(self.tool_parser, ToolParser):
            return self.tool_parser

        if not isinstance(scanner, MarkerScanner):
            return None

        for body in self._iter_marker_bodies(scanner, samples):
            for parser in _KNOWN_TOOL_PARSERS.values():
                if parser.detect(body):
                    return parser

        return None

    @staticmethod
    def _iter_marker_bodies(scanner: MarkerScanner, samples: t.Iterable[str]) -> t.Iterator[str]:
        """Yield every non-empty body slice between *scanner*'s open and close literals across *samples*.

        For two-sided markers (``scanner.end`` is set), every well-formed pair in the sample is yielded in order;
        the first unmatched open literal terminates the walk for that sample. For one-sided markers (``end is
        None``), only the body following the first open literal is yielded — up to :data:`TEMPLATE_BODY_MAX_CHARS`
        — since there's no closing anchor to repeat against.
        """
        for sample in samples:
            if not sample:
                continue
            pos = 0
            while (start := sample.find(scanner.start, pos)) >= 0:
                body_start = start + len(scanner.start)
                if scanner.end is None:
                    if body := sample[body_start : body_start + TEMPLATE_BODY_MAX_CHARS].strip():
                        yield body
                    break
                end = sample.find(scanner.end, body_start)
                if end < 0:
                    break
                if body := sample[body_start:end].strip():
                    yield body
                pos = end + len(scanner.end)
