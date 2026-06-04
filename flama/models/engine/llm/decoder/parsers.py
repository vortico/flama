import abc
import ast
import dataclasses
import json
import re
import typing as t

__all__ = [
    "CallNotationParser",
    "JSONArrayParser",
    "JSONNamedSequenceParser",
    "JSONObjectParser",
    "JSONSequenceParser",
    "PassthroughParser",
    "PythonicParser",
    "ToolCall",
    "ToolParser",
]


@dataclasses.dataclass(frozen=True)
class ToolCall:
    """One parsed tool-call extracted from a marker-pair body.

    Carries the dispatchable payload (function name + parsed arguments) without an id; the framework mints ids
    per stream as :class:`ToolCall` instances flow into :class:`~flama.models.ToolEvent`.

    :param name: Function name advertised by the model.
    :param arguments: Parsed argument object (already coerced to native types where possible).
    """

    name: str
    arguments: dict[str, t.Any]


@dataclasses.dataclass(frozen=True)
class ToolParser(abc.ABC):
    """Stateless body-to-calls parser.

    Implementations are pure: :meth:`parse` takes the entire tool-marker body and yields one :class:`ToolCall`
    per call discovered. Instances are immutable and shareable across streams, so registries store instances
    directly.

    The default :meth:`detect` runs :meth:`parse` against a sample body and returns whether the parser extracts
    at least one named call; subclasses override only when they need a cheaper or stricter check (e.g.
    :class:`PassthroughParser`, which is never a winning auto-detection candidate).

    :param name: Registry key used for logs and identity; declared keyword-only with an empty default so concrete
        subclasses are free to introduce non-defaulted positional fields without violating the
        defaults-after-non-defaults dataclass rule.
    """

    name: str = dataclasses.field(default="", kw_only=True)

    @abc.abstractmethod
    def parse(self, body: str, /) -> t.Iterator[ToolCall]:
        """Yield one :class:`ToolCall` per call found in *body*."""
        ...

    def detect(self, body: str, /) -> bool:
        """True iff this parser extracts at least one named call from *body*.

        Used by :meth:`Decoder._detect_tool_parser` to pick a parser by trying each candidate against the example
        body sliced from a chat-template or preflight sample. The "named call" check filters out
        :class:`PassthroughParser`-shaped fallbacks without requiring subclasses to opt out explicitly.
        """
        return any(call.name for call in self.parse(body))


@dataclasses.dataclass(frozen=True)
class JSONParser(ToolParser):
    """Abstract base for JSON-shaped tool-body parsers.

    Subclasses implement :meth:`_iter_calls`, the lexer for their body shape; the inherited :meth:`parse` simply
    forwards into it. :meth:`_build_call` lifts a parsed dict into a :class:`ToolCall` using the configured name
    / args field rules - subclasses with extra construction inputs (e.g. a prefix name) override it to fold
    them in.

    :param args_fields: Candidate JSON keys to extract arguments from. Tried in order.
    :param name_field: JSON key carrying the function name.
    """

    args_fields: t.Sequence[str] = ("arguments", "parameters")
    name_field: str = "name"

    def parse(self, body: str, /) -> t.Iterator[ToolCall]:
        yield from self._iter_calls(body.strip())

    @abc.abstractmethod
    def _iter_calls(self, s: str, /) -> t.Iterator[ToolCall]:
        """Yield one :class:`ToolCall` per parsed segment in *s*."""
        ...

    def _build_call(self, obj: dict[str, t.Any], /) -> ToolCall:
        """Build a :class:`ToolCall` from a parsed dict using :attr:`name_field` and :attr:`args_fields`."""
        return ToolCall(
            name=str(obj.get(self.name_field, "")),
            arguments=next((obj[f] for f in self.args_fields if f in obj and isinstance(obj[f], dict)), {}),
        )


@dataclasses.dataclass(frozen=True)
class JSONObjectParser(JSONParser):
    """One ``{"name": ..., "arguments": {...}}`` object per body.

    Used by Hermes-style ``<tool_call>{...}</tool_call>`` formats.
    """

    def _iter_calls(self, s: str, /) -> t.Iterator[ToolCall]:
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            return

        if isinstance(obj, dict):
            yield self._build_call(obj)


@dataclasses.dataclass(frozen=True)
class JSONArrayParser(JSONParser):
    """One JSON array of name+args objects per body.

    Used by Mistral pre-v11 ``[TOOL_CALLS][{...}, {...}]`` formats.
    """

    def _iter_calls(self, s: str, /) -> t.Iterator[ToolCall]:
        try:
            obj_list = json.loads(s)
        except json.JSONDecodeError:
            return

        if isinstance(obj_list, list):
            for obj in obj_list:
                if isinstance(obj, dict):
                    yield self._build_call(obj)


@dataclasses.dataclass(frozen=True)
class JSONSequenceParser(JSONParser):
    """Stream of ``{json}`` segments per body, parsed greedily via :class:`json.JSONDecoder.raw_decode`.

    Each segment is a self-describing dict carrying both name and args (read via :attr:`name_field` and
    :attr:`args_fields`); an optional :attr:`separator` literal between calls is supported. Used by Llama 3
    ``python_tag`` formats (``separator="; "``).

    :param separator: Optional literal between calls.
    """

    separator: str | None = None

    _HEAD_RE: t.ClassVar[re.Pattern[str]] = re.compile(r"\s*(?=\{)")

    def _iter_calls(self, s: str, /) -> t.Iterator[ToolCall]:
        decoder = json.JSONDecoder()
        pos = 0
        while head := self._HEAD_RE.match(s, pos):
            try:
                obj, pos = decoder.raw_decode(s, head.end())
            except json.JSONDecodeError:
                return

            yield self._build_call(obj)

            if self.separator and s.startswith(self.separator, pos):
                pos += len(self.separator)


@dataclasses.dataclass(frozen=True)
class JSONNamedSequenceParser(JSONParser):
    """Stream of ``NAME{json_args}`` segments per body, with the function name as a positional prefix.

    Used by Mistral v11+ formats where the tool marker repeats per call: a bare identifier names the call and
    the trailing ``{...}`` dict supplies the arguments verbatim.

    :param separator: Optional literal between calls.
    """

    separator: str | None = None

    _HEAD_RE: t.ClassVar[re.Pattern[str]] = re.compile(r"\s*([A-Za-z_][\w\.\-]*)\s*(?=\{)")

    def _iter_calls(self, s: str, /) -> t.Iterator[ToolCall]:
        decoder = json.JSONDecoder()
        pos = 0
        while head := self._HEAD_RE.match(s, pos):
            try:
                obj, pos = decoder.raw_decode(s, head.end())
            except json.JSONDecodeError:
                return

            if isinstance(obj, dict):
                yield self._build_call(obj, prefix_name=head.group(1))

            if self.separator and s.startswith(self.separator, pos):
                pos += len(self.separator)

    def _build_call(self, obj: dict[str, t.Any], /, *, prefix_name: str = "") -> ToolCall:
        """Build a :class:`ToolCall` whose ``name`` comes from the consumed positional prefix."""
        return ToolCall(name=prefix_name, arguments=obj)


@dataclasses.dataclass(frozen=True)
class PythonicParser(ToolParser):
    """Python AST parser for ``[func(kw=val, ...), ...]`` bodies.

    Used by Llama 3.2 / 4 ``pythonic`` and ``python_block`` formats and by Granite. The body is parsed via
    :func:`ast.parse`; :meth:`_iter_calls` yields one :class:`ToolCall` per ``ast.Call`` element that resolves
    to a non-empty dotted name.
    """

    def parse(self, body: str, /) -> t.Iterator[ToolCall]:
        yield from self._iter_calls(body.strip())

    def _iter_calls(self, body: str, /) -> t.Iterator[ToolCall]:
        """Yield one :class:`ToolCall` per resolvable ``ast.Call`` inside *body*."""
        candidate = body if body.startswith("[") else f"[{body}]"
        try:
            parsed = ast.parse(candidate, mode="eval")
        except SyntaxError:
            return

        if not isinstance(parsed.body, ast.List):
            return

        for element in parsed.body.elts:
            if isinstance(element, ast.Call) and (call := self._build_call(element)) is not None:
                yield call

    def _build_call(self, call: ast.Call, /) -> ToolCall | None:
        """Lift an ``ast.Call`` to a :class:`ToolCall`; return :data:`None` for nameless calls."""
        if not (name := self._ast_call_name(call.func)):
            return None

        args: dict[str, t.Any] = {}
        for kw in call.keywords:
            if kw.arg is None:
                continue

            try:
                args[kw.arg] = ast.literal_eval(kw.value)
            except (ValueError, SyntaxError):
                ...

        return ToolCall(name=name, arguments=args)

    @staticmethod
    def _ast_call_name(func: ast.expr) -> str:
        """Render the function expression of an ``ast.Call`` as a dotted name string."""
        match func:
            case ast.Name(id=name):
                return name
            case ast.Attribute(value=value, attr=attr):
                prefix = PythonicParser._ast_call_name(value)
                return f"{prefix}.{attr}" if prefix else attr
            case _:
                return ""


@dataclasses.dataclass(frozen=True)
class CallNotationParser(ToolParser):
    """``[prefix]NAME{key:value,...}`` body with bare unquoted keys and custom string delimiters.

    Used by Gemma 4's ``<|tool_call>call:NAME{k:<|"|>v<|"|>}<tool_call|>`` format. Multiple calls are supported
    (the body may contain several ``call:NAME{...}`` segments back-to-back, separated by whitespace).

    Two per-instance regexes - :attr:`_head_re` and :attr:`_pair_re` - bake :attr:`prefix`, :attr:`string_open`,
    and :attr:`string_close` into compiled patterns at construction time, so :meth:`_iter_calls` reduces to a
    walrus-loop over ``_head_re`` and :meth:`_parse_kv` to a walrus-loop over ``_pair_re``.

    :param prefix: Literal preceding the function name (``"call:"`` for Gemma 4).
    :param string_open: Literal opening a string value (``'<|"|>'`` for Gemma 4).
    :param string_close: Literal closing a string value.
    """

    prefix: str = "call:"
    string_open: str = '<|"|>'
    string_close: str = '<|"|>'

    _head_re: re.Pattern[str] = dataclasses.field(init=False, repr=False, compare=False)
    _pair_re: re.Pattern[str] = dataclasses.field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_head_re",
            re.compile(rf"\s*(?:{re.escape(self.prefix)})?\s*([A-Za-z_][\w\.\-]*)\s*\{{"),
        )
        object.__setattr__(
            self,
            "_pair_re",
            re.compile(
                rf"\s*([A-Za-z_]\w*)\s*:\s*"
                rf"(?:{re.escape(self.string_open)}(?P<quoted>.*?){re.escape(self.string_close)}"
                rf"|(?P<bare>[^,}}]+))"
                rf"\s*,?\s*",
                re.DOTALL,
            ),
        )

    def parse(self, body: str, /) -> t.Iterator[ToolCall]:
        yield from self._iter_calls(body.strip())

    def _iter_calls(self, s: str, /) -> t.Iterator[ToolCall]:
        pos = 0
        while head := self._head_re.match(s, pos):
            args, pos = self._parse_kv(s, head.end())
            if pos < 0:
                return

            yield self._build_call(name=head.group(1), args=args)

    def _build_call(self, *, name: str, args: dict[str, t.Any]) -> ToolCall:
        """Mint a :class:`ToolCall` from the matched name and parsed KV args."""
        return ToolCall(name=name, arguments=args)

    def _parse_kv(self, s: str, pos: int, /) -> tuple[dict[str, t.Any], int]:
        """Parse a KV body starting just past ``{``; return ``(args, pos_after_})`` or ``(_, -1)`` on failure."""
        args: dict[str, t.Any] = {}
        while pos < len(s):
            if s[pos] == "}":
                return args, pos + 1
            if not (pair := self._pair_re.match(s, pos)):
                return args, -1
            args[pair.group(1)] = (
                pair.group("quoted")
                if pair.group("quoted") is not None
                else self._coerce_literal(pair.group("bare").strip())
            )
            pos = pair.end()
        return args, -1

    @staticmethod
    def _coerce_literal(raw: str) -> t.Any:
        """Best-effort literal coercion (number / bool / null / fallback to string)."""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw


@dataclasses.dataclass(frozen=True)
class PassthroughParser(ToolParser):
    """Parser that surfaces a non-parseable tool body as a single empty-named call.

    Used when a tool marker is identified but the body format cannot be recognised. A non-empty body yields one
    :class:`ToolCall` with an empty ``name`` and ``arguments``; downstream consumers receive a
    :class:`~flama.models.ToolEvent` they can still surface as an opaque, unparsed call.
    """

    name: t.Final[t.Literal["passthrough"]] = dataclasses.field(default="passthrough", kw_only=True)

    def parse(self, body: str, /) -> t.Iterator[ToolCall]:
        if body:
            yield ToolCall(name="", arguments={})

    def detect(self, body: str, /) -> bool:
        """Always :data:`False`; passthrough is the explicit fallback, never auto-detected."""
        return False
