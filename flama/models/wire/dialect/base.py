import abc
import typing as t

from flama import compat
from flama.models.exceptions import LLMGenerationError
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    AudioFormat,
    Content,
    ImageFormat,
    Message,
    SystemMessage,
    TextContent,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from flama.models.transport.input.llm.tool import Tool
from flama.models.transport.output.llm.buffer import EventBuffer
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent

__all__ = ["Assembler", "CoalescingRenderer", "Dialect", "Parser", "Renderer"]

_T = t.TypeVar("_T")
_W = t.TypeVar("_W")
_ParserKind: t.TypeAlias = t.Literal["messages", "tools"]
_CoalescingState: t.TypeAlias = t.Literal["idle", "buffering"]


class _RenderKwargs(t.TypedDict, total=False):
    """Marker base for per-dialect render kwargs TypedDicts.

    Subclasses declare the dialect-specific keyword shape consumed by :meth:`Dialect.render`. Empty body so
    every concrete render-kwargs TypedDict starts from a clean payload; the inheritance only exists to bind
    the :data:`_RK` TypeVar.
    """


class _AssembleKwargs(t.TypedDict, total=False):
    """Marker base for per-dialect assemble kwargs TypedDicts.

    Subclasses declare the dialect-specific keyword shape consumed by :meth:`Dialect.assemble`. Empty body so
    every concrete assemble-kwargs TypedDict starts from a clean payload; the inheritance only exists to
    bind the :data:`_AK` TypeVar.
    """


_RK = t.TypeVar("_RK", bound=_RenderKwargs)
_AK = t.TypeVar("_AK", bound=_AssembleKwargs)


class Parser(abc.ABC):
    """Wire to transport input strategy (L1 -> L2).

    Concrete dialects subclass :class:`Parser` and override :meth:`_parse_part` (and, when the wire shape needs
    pre-normalisation, the :meth:`_canonicalize_message` hook; for 1:N message expansion the
    :meth:`_parse_messages` hook; for list-level tool normalization the :meth:`_parse_tools` hook).
    The shared :meth:`_parse_message` template owns the universal role / content / ``tool_calls`` /
    ``tool_call_id`` parsing skeleton; :meth:`_parse_tool` plus :meth:`_parse_tool_call` carry the
    OpenAI-style ``tools`` / ``tool_calls`` envelope reused across every dialect Flama speaks today.

    Public surface is the single :meth:`parse` dispatcher; callers select between message-list and tool-list
    parsing via the ``kind`` discriminator. Used by :class:`Dialect` via the :attr:`Dialect.PARSER` class
    binding; callers normally invoke parsing through :meth:`Dialect.parse` (a thin forwarder) and only reach
    the parser surface directly when targeting a specific dialect's parser in tests or low-level tooling.

    :cvar IMAGE_FORMATS: Allowed image format hints, derived from
        :data:`flama.models.transport.input.llm.message.ImageFormat`.
    :cvar AUDIO_FORMATS: Allowed audio format hints, derived from
        :data:`flama.models.transport.input.llm.message.AudioFormat`.
    """

    IMAGE_FORMATS: t.ClassVar[tuple[ImageFormat, ...]] = t.get_args(ImageFormat)
    AUDIO_FORMATS: t.ClassVar[tuple[AudioFormat, ...]] = t.get_args(AudioFormat)

    @t.overload
    @classmethod
    def parse(
        cls,
        value: list[dict[str, t.Any]],
        /,
        *,
        kind: t.Literal["messages"],
        system: t.Any = None,
    ) -> tuple[Message, ...]: ...
    @t.overload
    @classmethod
    def parse(cls, value: list[t.Any], /, *, kind: t.Literal["tools"]) -> tuple[Tool, ...]: ...
    @classmethod
    def parse(
        cls,
        value: t.Any,
        /,
        *,
        kind: _ParserKind,
        system: t.Any = None,
    ) -> tuple[Message, ...] | tuple[Tool, ...]:
        """Translate a dialect-shaped wire payload into a tuple of canonical L2 typed objects.

        Pure dispatcher: forwards to :meth:`_parse_messages` (with the optional top-level *system*
        payload) or :meth:`_parse_tools` based on *kind*. Static return-type narrowing is provided
        by the literal :class:`~typing.overload` declarations.

        :param value: Wire payload — a list of message dicts for ``kind="messages"`` or a list of tool
            elements for ``kind="tools"``.
        :param kind: Either ``"messages"`` (-> :class:`tuple` of :class:`~flama.models.Message`) or
            ``"tools"`` (-> :class:`tuple` of :class:`~flama.models.transport.input.llm.tool.Tool`).
        :param system: Optional top-level system payload accepted alongside ``kind="messages"``. Default
            :class:`Parser` raises when a non-``None`` value is supplied; dialects that carry ``system``
            outside the ``messages`` array (Anthropic) override :meth:`_parse_messages` to consume it.
        :raises ValueError: On structural violations propagated from :meth:`_parse_messages` /
            :meth:`_parse_tools`, or when *kind* is unknown.
        """
        match kind:
            case "messages":
                return cls._parse_messages(value, system=system)
            case "tools":
                return cls._parse_tools(value)
            case _:
                raise ValueError(f"Wrong kind {kind!r}, expected one of: ['messages', 'tools']")

    @classmethod
    def _parse_messages(cls, values: list[dict[str, t.Any]], /, *, system: t.Any = None) -> tuple[Message, ...]:
        """Translate the dialect's ``messages`` list into canonical L2 :class:`Message` instances.

        Default 1:1 implementation: forwards each element through :meth:`_parse_message`. Dialects whose
        wire shape needs 1:N expansion (Anthropic's multi-``tool_result`` user turns / assistant
        ``tool_use`` / ``thinking`` block split) or that carry the conversation's system prompt as a
        top-level field override this hook. The default rejects a non-``None`` *system* loudly so that
        a misrouted Anthropic payload to an OpenAI / Ollama / Native parser surfaces a clear error.

        :param values: Raw wire ``messages`` list.
        :param system: Optional top-level ``system`` payload. Default rejects non-``None`` values; the
            Anthropic override flattens it and prepends a leading :class:`SystemMessage`.
        :raises ValueError: On per-element violations, or when *system* is supplied and the dialect
            does not accept it.
        """
        if system is not None:
            raise ValueError(f"{cls.__name__} does not accept a top-level 'system' field")
        return tuple(cls._parse_message(v) for v in values)

    @classmethod
    def _parse_tools(cls, values: list[t.Any], /) -> tuple[Tool, ...]:
        """Translate the dialect's ``tools`` list into canonical L2 :class:`Tool` instances.

        Default 1:1 implementation: forwards each element through :meth:`_parse_tool`. Dialects whose
        wire shape needs list-level normalization (deduplication, ordering invariants, list-level
        metadata) override this hook; per-element shape concerns stay on :meth:`_parse_tool`.

        :param values: Raw wire ``tools`` list.
        :raises ValueError: On per-element violations.
        """
        return tuple(cls._parse_tool(v) for v in values)

    @classmethod
    def _parse_message(cls, value: dict[str, t.Any]) -> Message:  # noqa: C901
        """Translate a dialect-shaped message dict into a canonical L2 :class:`Message`.

        Template method: pre-normalises *value* via :meth:`_canonicalize_message`, walks the universal
        ``content`` / ``tool_calls`` skeleton (delegating per-part typing to :meth:`_parse_part`),
        rejects role-incompatible wire fields, and dispatches on ``role`` to the matching concrete
        :class:`Message` subclass. Per-role required-field checks ("``content`` is required for ``X``
        messages") live here so error messages stay role-specific; structural and L2 type invariants
        ("``tool_call_id`` must be a string", "``X`` messages only support text content") are owned by
        each subclass's ``__post_init__``.

        :param value: Raw wire dict.
        :raises ValueError: On wire-shape violations (missing ``role``, malformed ``content`` /
            ``tool_calls`` shape, role-incompatible fields, ...) or invariants from the constructed
            subclass.
        """
        value = cls._canonicalize_message(value)
        if not isinstance(value, dict) or "role" not in value:
            raise ValueError("Wrong message, expected an object with at least a 'role' field")
        role = value["role"]

        if role != "tool" and value.get("tool_call_id") is not None:
            raise ValueError("'tool_call_id' is only allowed when role is 'tool'")
        if role != "assistant" and value.get("tool_calls") is not None:
            raise ValueError("'tool_calls' is only allowed when role is 'assistant'")
        if role != "assistant" and value.get("reasoning_content") is not None:
            raise ValueError("'reasoning_content' is only allowed when role is 'assistant'")

        content: tuple[Content, ...] | None = None
        if (raw := value.get("content")) is not None:
            if isinstance(raw, str):
                content = (TextContent(text=raw),)
            elif isinstance(raw, list):
                content = tuple(cls._parse_part(part) for part in raw)
            else:
                raise ValueError("'content' must be a string or a list of content parts")

        tool_calls: tuple[ToolCall, ...] | None = None
        if (raw := value.get("tool_calls")) is not None:
            if not isinstance(raw, list):
                raise ValueError("'tool_calls' must be a list of objects")
            tool_calls = tuple(cls._parse_tool_call(c) for c in raw)

        match role:
            case "system":
                if content is None:
                    raise ValueError("'content' is required for 'system' messages")
                return SystemMessage(content=content)
            case "user":
                if content is None:
                    raise ValueError("'content' is required for 'user' messages")
                return UserMessage(content=content)
            case "assistant":
                return AssistantMessage(
                    content=content,
                    tool_calls=tool_calls,
                    reasoning_content=value.get("reasoning_content"),
                )
            case "tool":
                if content is None:
                    raise ValueError("'content' is required for 'tool' messages")
                tool_call_id = value.get("tool_call_id")
                if tool_call_id is None:
                    raise ValueError("'tool_call_id' is required for 'tool' messages")
                return ToolMessage(content=content, tool_call_id=tool_call_id)
            case _:
                raise ValueError(f"Wrong role '{role}', expected one of: ['system', 'user', 'assistant', 'tool']")

    @classmethod
    def _parse_tool(cls, value: t.Any) -> Tool:
        """Translate a dialect ``tools`` element into a canonical L2 :class:`Tool`.

        Wire-shape pre-conditions live here (envelope is a dict, ``type`` pins to ``"function"``,
        ``function`` is an object); per-field type and value invariants are owned by
        :meth:`Tool.__post_init__` so they apply equally to direct construction.
        """
        if not isinstance(value, dict):
            raise ValueError("tools element must be an object")
        raw_type = value.get("type", "function")
        if raw_type != "function":
            raise ValueError(f"Wrong tool type '{raw_type}', expected 'function'")
        function = value.get("function")
        if not isinstance(function, dict):
            raise ValueError("tools element must carry a 'function' object")
        return Tool(
            name=function.get("name"),
            description=function.get("description"),
            parameters=function.get("parameters", {}),
        )

    @classmethod
    @abc.abstractmethod
    def _parse_part(cls, part: t.Any) -> Content:
        """Translate a raw dialect content-part dict into a typed :class:`Content` instance.

        :param part: Raw dict from the wire. Must carry a ``type`` discriminator whose accepted values are
            dialect-specific.
        :return: Typed :class:`Content` instance.
        :raises ValueError: If *part* is not a dict, is missing ``type``, or carries malformed payload values.
        :raises LLMUnsupportedContentPart: If *part* carries a ``type`` the serving layer does not support.
        """
        ...

    @classmethod
    def _canonicalize_message(cls, value: t.Any, /) -> t.Any:
        """Pre-normalise a dialect-shaped message dict before the shared parsing skeleton consumes it.

        Default identity. Dialects whose wire shape does not match the canonical structured-content shape (e.g.
        Ollama spliced ``images: [...]`` siblings) override this hook to splice their wire quirks into a uniform
        payload before :meth:`_parse_message` parses it.
        """
        return value

    @classmethod
    def _parse_tool_call(cls, value: t.Any) -> ToolCall:
        """Translate a dialect ``tool_calls`` element into a canonical :class:`ToolCall`.

        Wire-shape pre-conditions live here (envelope is a dict, ``function`` is an object); per-field
        type invariants are owned by :meth:`ToolCall.__post_init__`.
        """
        if not isinstance(value, dict):
            raise ValueError("tool_calls element must be an object")
        function = value.get("function")
        if not isinstance(function, dict):
            raise ValueError("tool_calls element must carry a 'function' object")
        return ToolCall(function=dict(function), id=value.get("id"))

    @staticmethod
    def _format_from_data_uri(url: str, /, *, allowed: t.Collection[str], default: str) -> str:
        """Extract the ``data:`` URI media-type suffix, falling back to *default* when missing or unsupported."""
        header, _, _ = url.partition(",")
        media = header[5:].split(";", 1)[0].strip()
        if "/" in media:
            media = media.split("/", 1)[1]
        media = media.lower()
        return media if media in allowed else default


class Renderer(abc.ABC, t.Generic[_T]):
    """Transport to wire output strategy (L2 -> L1).

    Per-event-type FSM strategy driving the :class:`~flama.models.transport.output.llm.buffer.EventBuffer`
    engine. Each ``on_<kind>`` method receives a typed L2 :class:`~flama.models.Event` and yields zero or more
    outputs of type ``_T`` (the wire format the renderer projects). The engine extends its internal pending
    queue with the iterable returned by each call, so generator-based renderers compose cleanly with
    terminal-based ones.

    :meth:`flush` is invoked by the engine once before each :meth:`on_stop` call (so renderers can drain open
    FSM state before the terminal frame) and once more on source exhaustion (so trailing buffered state
    surfaces even when the source ends without a :class:`~flama.models.StopEvent`).

    The :attr:`skip` instance attribute drives the engine's leading-output suppression count: the engine
    discards the first ``skip`` outputs before yielding any frames downstream. Resume-aware renderers seed
    this from a recovered sequence number; fresh renderers leave it at the default ``0``.

    Used by :class:`Dialect.render` (composes a per-format :class:`Renderer` with the engine to project a
    source as a stream of wire frames) and :class:`Dialect.assemble` (composes :class:`CoalescingRenderer`
    with the engine to drain the source as a tuple of L2 events for buffered envelope construction).
    """

    skip: int = 0

    def on_start(self, block: StartEvent) -> t.Iterable[_T]:
        """Translate the opening lifecycle marker. Default: no-op (most renderers do not surface it)."""
        return ()

    @abc.abstractmethod
    def on_text(self, block: TextEvent) -> t.Iterable[_T]:
        """Translate a content text fragment."""
        ...

    @abc.abstractmethod
    def on_tool(self, block: ToolEvent) -> t.Iterable[_T]:
        """Translate a complete tool-call event."""
        ...

    def on_trace(self, block: TraceEvent) -> t.Iterable[_T]:
        """Translate an out-of-band telemetry trace. Default: no-op (only the native dialect uses traces)."""
        return ()

    @abc.abstractmethod
    def on_stop(self, block: StopEvent) -> t.Iterable[_T]:
        """Translate the terminal lifecycle marker. Called *after* :meth:`flush`."""
        ...

    def flush(self) -> t.Iterable[_T]:
        """Drain any open FSM state. Default: no-op; override only when the renderer buffers state across events."""
        return ()


class CoalescingRenderer(Renderer[Event]):
    """Default L2 -> L2 strategy.

    Coalesces consecutive same-channel :class:`~flama.models.TextEvent` instances into a single concatenated
    event, passes :class:`~flama.models.ToolEvent` through verbatim, and drops
    :class:`~flama.models.TraceEvent` and lifecycle markers from the output stream. Used by
    :meth:`Dialect.assemble` as the default L2-only renderer, and by serving paths that need a buffered tuple
    of events for envelope construction.
    """

    def __init__(self) -> None:
        self._state: _CoalescingState = "idle"
        self._channel: str | None = None
        self._buffer: list[str] = []

    def on_text(self, block: TextEvent) -> t.Iterable[Event]:
        if self._state == "buffering" and self._channel != block.channel:
            yield from self.flush()
        self._state = "buffering"
        self._channel = block.channel
        self._buffer.append(block.text)

    def on_tool(self, block: ToolEvent) -> t.Iterable[Event]:
        yield from self.flush()
        yield block

    def on_stop(self, block: StopEvent) -> t.Iterable[Event]:
        return ()

    def flush(self) -> t.Iterable[Event]:
        if self._state == "buffering":
            yield TextEvent(channel=self._channel, text="".join(self._buffer))
            self._state = "idle"
            self._channel = None
            self._buffer = []


class Assembler(abc.ABC, t.Generic[_AK]):
    """Transport to wire buffered envelope strategy (L2 -> L1, single shot).

    Symmetric to :class:`Parser` (L1 -> L2 input) and :class:`Renderer` (L2 -> L1 streaming output).
    Receives the drained, coalesced :class:`~flama.models.Event` tuple plus the captured lifecycle markers
    and returns the dialect's buffered envelope dict.

    Used by :class:`Dialect.assemble` via the :attr:`Dialect.ASSEMBLER` class binding; callers normally
    invoke envelope construction through :meth:`Dialect.assemble` (which composes the engine with
    :class:`CoalescingRenderer`, drains, surfaces mid-stream failures via
    :class:`~flama.models.exceptions.LLMGenerationError`, and relays to :meth:`envelope`). Dialects whose
    wire has no buffered shape (e.g. the native channel-tagged stream) implement :meth:`envelope` to raise
    :class:`NotImplementedError`.

    The generic parameter ``_AK`` is the dialect-specific :class:`~typing.TypedDict` describing the kwargs
    accepted by :meth:`envelope`; type-checked through PEP 692 ``Unpack`` on
    :meth:`Dialect.assemble`'s ``**kwargs``.
    """

    @classmethod
    @abc.abstractmethod
    def envelope(
        cls,
        events: tuple[Event, ...],
        /,
        *,
        start: StartEvent,
        stop: StopEvent,
        **kwargs: compat.Unpack[_AK],
    ) -> dict[str, t.Any]:
        """Translate a drained event tuple into the dialect's buffered envelope dict.

        :param events: Tuple of :class:`~flama.models.Event` blocks the engine emitted (after
            :class:`CoalescingRenderer` collapsed consecutive same-channel text fragments and dropped lifecycle
            markers / traces).
        :param start: Captured opening lifecycle marker; carries ``input_tokens`` for usage tallies.
        :param stop: Captured terminal lifecycle marker; carries ``stop_reason`` and ``output_tokens``.
        :param kwargs: Dialect-specific kwargs typed by ``_AK`` (envelope identity, mode flags, ...).
        :return: JSON-serialisable envelope dict matching the dialect's wire schema.
        :raises NotImplementedError: When the dialect has no buffered envelope shape.
        """
        ...


class Dialect(abc.ABC, t.Generic[_W, _RK, _AK]):
    """Wire to transport bridge (L1 <-> L2 façade).

    Concrete dialects bind three strategies as class-level :class:`~typing.ClassVar` declarations and
    introduce dialect-specific :class:`~typing.TypedDict` shapes for the render / assemble kwargs:

    - :attr:`PARSER` -> a :class:`Parser` subclass (L1 -> L2 input parsing).
    - :attr:`RENDERER` -> a :class:`Renderer` subclass (L2 -> L1 streaming output).
    - :attr:`ASSEMBLER` -> an :class:`Assembler` subclass (L2 -> L1 buffered envelope construction).

    The base :meth:`parse`, :meth:`render`, and :meth:`assemble` methods are concrete relays into the bound
    strategies; concrete dialects do not override them. The dialect façade is a pure declaration of the
    binding, not a behaviour declaration.

    The generic parameters are:

    - ``_W``: wire frame type emitted by :meth:`render`
      (e.g. :class:`~flama.http.responses.sse.ServerSentEvent` for SSE dialects,
      :data:`~flama.types.JSONSchema` for NDJSON dialects).
    - ``_RK``: dialect-specific :class:`~typing.TypedDict` describing the kwargs accepted by :meth:`render`.
    - ``_AK``: dialect-specific :class:`~typing.TypedDict` describing the kwargs accepted by :meth:`assemble`.
    """

    PARSER: t.ClassVar[type[Parser]]
    RENDERER: t.ClassVar[type[Renderer]]
    ASSEMBLER: t.ClassVar[type[Assembler]]

    @t.overload
    @classmethod
    def parse(
        cls,
        value: list[dict[str, t.Any]],
        /,
        *,
        kind: t.Literal["messages"],
        system: t.Any = None,
    ) -> tuple[Message, ...]: ...
    @t.overload
    @classmethod
    def parse(cls, value: list[t.Any], /, *, kind: t.Literal["tools"]) -> tuple[Tool, ...]: ...
    @classmethod
    def parse(
        cls,
        value: t.Any,
        /,
        *,
        kind: _ParserKind,
        system: t.Any = None,
    ) -> tuple[Message, ...] | tuple[Tool, ...]:
        """Translate a dialect-shaped wire payload into a tuple of canonical L2 typed objects.

        Thin forwarder to :meth:`PARSER.parse <Parser.parse>`. Static return-type narrowing is provided
        by the literal :class:`~typing.overload` declarations.

        :param value: Wire payload — list of message dicts for ``kind="messages"`` or list of tool
            elements for ``kind="tools"``.
        :param kind: ``"messages"`` (-> tuple of :class:`~flama.models.Message`) or ``"tools"``
            (-> tuple of :class:`~flama.models.transport.input.llm.tool.Tool`).
        :param system: Optional top-level system payload accepted alongside ``kind="messages"``;
            consumed only by dialects that carry ``system`` outside the ``messages`` array.
        :raises ValueError: On structural violations propagated from the bound parser.
        """
        if kind == "messages":
            return cls.PARSER.parse(value, kind=kind, system=system)
        return cls.PARSER.parse(value, kind=kind)

    @classmethod
    def render(
        cls,
        source: t.Iterable[Event] | t.AsyncIterable[Event],
        /,
        **kwargs: compat.Unpack[_RK],
    ) -> t.AsyncIterator[_W]:
        """Project an :class:`~flama.models.Event` source as a stream of wire frames.

        Constructs a fresh :attr:`RENDERER` from *kwargs* (which match the dialect-bound ``_RK`` TypedDict)
        and drives it through :class:`~flama.models.transport.output.llm.buffer.EventBuffer`. The method is
        synchronous and returns an :class:`~typing.AsyncIterator` so callers can drive it with ``async for``
        directly.

        :param source: Sync or async iterable of :class:`~flama.models.Event` blocks (lists, generators, or a
            :class:`~flama.models.streams.StreamBuffer`).
        :return: Async iterator yielding wire frames of type ``_W``.
        """
        return EventBuffer(source, cls.RENDERER(**kwargs))

    @classmethod
    async def assemble(
        cls,
        source: t.Iterable[Event] | t.AsyncIterable[Event],
        /,
        **kwargs: compat.Unpack[_AK],
    ) -> dict[str, t.Any]:
        """Project an :class:`~flama.models.Event` source as a single buffered envelope.

        Drains *source* through :class:`~flama.models.transport.output.llm.buffer.EventBuffer` with a
        :class:`CoalescingRenderer`, raises :class:`~flama.models.exceptions.LLMGenerationError` on
        mid-stream failure (terminal :class:`~flama.models.StopEvent` carries ``stop_reason='error'``), and
        relays the drained event tuple plus captured lifecycle markers to :attr:`ASSEMBLER`'s
        :meth:`Assembler.envelope` for dialect-specific envelope construction.

        :param source: Sync or async iterable of :class:`~flama.models.Event` blocks.
        :return: JSON-serialisable envelope dict matching the dialect's wire schema.
        :raises ~flama.models.exceptions.LLMGenerationError: Generation failed mid-stream.
        :raises NotImplementedError: When the dialect has no buffered envelope shape (e.g. the native
            channel-tagged stream is stream-only).
        """
        buffer = EventBuffer(source, CoalescingRenderer())
        events = await buffer.assemble()
        if buffer.stop.stop_reason == "error":
            raise LLMGenerationError()
        return cls.ASSEMBLER.envelope(events, start=buffer.start, stop=buffer.stop, **kwargs)
