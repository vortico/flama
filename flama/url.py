import abc
import dataclasses
import decimal
import enum
import re
import typing as t
import urllib.parse
import uuid

from flama._core.url import MatchKind, NetlocMatcher, PathMatcher

T = t.TypeVar("T", bound=int | str | float | decimal.Decimal | uuid.UUID)
FragmentType = t.Literal["constant", "rest", "str", "int", "float", "decimal", "uuid"]

__all__ = ["Netloc", "Path", "URITemplate", "URL"]


class Serializer(t.Generic[T], metaclass=abc.ABCMeta):
    regex: t.ClassVar[re.Pattern]
    type: t.ClassVar[type]

    @abc.abstractmethod
    def load(self, value: str) -> T: ...

    @abc.abstractmethod
    def dump(self, value: T) -> str: ...

    def __eq__(self, other):
        return type(other) == type(self)


class StringSerializer(Serializer[str]):
    regex = re.compile(r"[^/]+")
    type = str

    def load(self, value: str) -> str:
        return str(value)

    def dump(self, value: str) -> str:
        return str(value)


class IntegerSerializer(Serializer[int]):
    regex = re.compile(r"-?[0-9]+")
    type = int

    def load(self, value: str) -> int:
        return int(value)

    def dump(self, value: int) -> str:
        return str(value)


class FloatSerializer(Serializer[float]):
    regex = re.compile(r"-?[0-9]+(.[0-9]+)?")
    type = float

    def load(self, value: str) -> float:
        return float(value)

    def dump(self, value: float) -> str:
        return f"{value:0.10f}".rstrip("0").rstrip(".")


class DecimalSerializer(Serializer[decimal.Decimal]):
    regex = re.compile(r"-?[0-9]+(.[0-9]+)?")
    type = decimal.Decimal

    def load(self, value: str) -> decimal.Decimal:
        return decimal.Decimal(value)

    def dump(self, value: decimal.Decimal) -> str:
        return str(value)


class UUIDSerializer(Serializer[uuid.UUID]):
    regex = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    type = uuid.UUID

    def load(self, value: str) -> uuid.UUID:
        return uuid.UUID(value)

    def dump(self, value: uuid.UUID) -> str:
        return str(value)


@dataclasses.dataclass
class _Fragment(abc.ABC):
    REGEX: t.ClassVar[re.Pattern] = re.compile(
        r"""
        (?P<parameter>{(?P<parameter_name>[a-zA-Z_][a-zA-Z0-9_]*)(?::(?P<parameter_type>[a-zA-Z_][a-zA-Z0-9_]*)?)?}) |
        (?P<constant>.*)
        """,
        re.X,
    )

    value: str
    type: FragmentType

    @classmethod
    def build(cls, fragment: str) -> "_Fragment":
        match = cls.REGEX.match(fragment)

        assert match

        if match.group("parameter"):
            return _FragmentParameter(
                value=fragment,
                type=t.cast(FragmentType, match.group("parameter_type") or "str"),
                name=match.group("parameter_name"),
            )
        else:
            return _FragmentConstant(value=fragment, type="constant")

    @property
    @abc.abstractmethod
    def regex(self) -> re.Pattern: ...

    @property
    @abc.abstractmethod
    def template(self) -> str: ...


@dataclasses.dataclass
class _FragmentConstant(_Fragment):
    @property
    def regex(self) -> re.Pattern:
        return re.compile(self.value)

    @property
    def template(self) -> str:
        return self.value


@dataclasses.dataclass
class _FragmentParameter(_Fragment):
    SERIALIZERS: t.ClassVar[dict[FragmentType, Serializer]] = {
        "str": StringSerializer(),
        "int": IntegerSerializer(),
        "float": FloatSerializer(),
        "decimal": DecimalSerializer(),
        "uuid": UUIDSerializer(),
    }

    name: str = dataclasses.field(repr=False, hash=False, compare=False)
    serializer: Serializer = dataclasses.field(init=False, repr=False, hash=False, compare=False)

    def __post_init__(self):
        try:
            self.serializer = self.SERIALIZERS[self.type]
        except KeyError:
            raise ValueError(f"Unknown path serializer '{self.type}'")

    @property
    def regex(self) -> re.Pattern:
        return re.compile(rf"(?P<{self.name}>{self.serializer.regex.pattern})")

    @property
    def template(self) -> str:
        return f"{{{self.name}}}"


class _Match(enum.Enum):
    exact = enum.auto()
    partial = enum.auto()
    none = enum.auto()


@dataclasses.dataclass
class _MatchResult:
    match: _Match
    parameters: dict[str, t.Any] | None
    matched: str | None
    unmatched: str | None


@dataclasses.dataclass
class _BuildResult:
    path: str
    unused: dict[str, t.Any]


class Path:
    Match = _Match

    def __init__(self, path: "str | Path"):
        """URL path with a regex to allow path params as placeholders.

        Given a path string like: "/foo/{bar:str}"
        path:        "/foo/{bar:str}"
        template:    "/foo/{bar}"
        regex:       "^/foo/(?P<bar>[^/]+)$"

        :param path: URL path.
        """
        if isinstance(path, Path):
            self.path = path.path
            self._fragments = path._fragments
            self._parameters = path._parameters
            self._regex = path._regex
            self._template = path._template
            self._matcher = path._matcher
            self._param_order = path._param_order
        else:
            if path != "" and not path.startswith("/"):
                raise ValueError("Path must starts with '/'")

            self.path = path
            self._fragments = [_Fragment.build(x) for x in path.strip("/").split("/")]
            self._parameters: dict[str, _FragmentParameter] = {
                f.name: f for f in self._fragments if isinstance(f, _FragmentParameter)
            }

            starting_slash = "/" if path != "" else ""
            trailing_slash = "/" if self.path != "/" and self.path.endswith("/") else ""

            fragments_templates = "/".join(f.template for f in self._fragments)
            self._template = f"{starting_slash}{fragments_templates}{trailing_slash}"

            fragments_regex = "/".join(f.regex.pattern for f in self._fragments)
            self._regex = re.compile(
                rf"^(?P<__matched__>{starting_slash}{fragments_regex}{trailing_slash})(?P<__unmatched__>.*)$"
            )

            segments = [
                (True, f.name, f.type) if isinstance(f, _FragmentParameter) else (False, f.value, "")
                for f in self._fragments
            ]
            self._matcher = PathMatcher(starting_slash != "", trailing_slash != "", segments)
            self._param_order = [f.name for f in self._fragments if isinstance(f, _FragmentParameter)]

    @property
    def parameters(self) -> dict[str, type]:
        return {f.name: f.serializer.type for f in self._parameters.values()}

    def match(self, path: "str | Path") -> _MatchResult:
        """Check if given path matches with current object.

        :param path: Path to match
        :return: Matching result, parameters serialized values and matching parts of the path.
        """
        result = self._matcher.match_path(str(path))
        if result is None:
            return _MatchResult(self.Match.none, None, None, None)

        match_kind, raw_values, matched, unmatched = result
        return _MatchResult(
            match=self.Match.partial if match_kind == MatchKind.Partial else self.Match.exact,
            parameters={
                name: self._parameters[name].serializer.load(raw_values[i]) for i, name in enumerate(self._param_order)
            },
            matched=matched,
            unmatched=unmatched,
        )

    def build(self, **params: t.Any) -> _BuildResult:
        """Build a path by completing param placeholders with given values.

        :param params: Param values.
        :return: Built path and unused params.
        """
        if not set(self._parameters.keys()) <= set(params.keys()):
            formatted_params = ", ".join(f"'{x}'" for x in self._parameters.keys())
            raise ValueError(f"Wrong params, expected: {formatted_params}.")

        return _BuildResult(
            path=self._template.format(
                **{k: self._parameters[k].serializer.dump(v) for k, v in params.items() if k in self._parameters}
            ),
            unused={k: v for k, v in params.items() if k not in self._parameters},
        )

    def __bool__(self) -> bool:
        return self.path != ""

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, other, /) -> bool:
        return isinstance(other, Path) and self.path.__eq__(other.path) or self.path.__eq__(other)

    def __str__(self) -> str:
        return self._template.__str__()

    def __repr__(self) -> str:
        return self.path.__repr__()

    def __truediv__(self, other: "str | Path") -> "Path":
        if isinstance(other, Path):
            a, b = self.path.rstrip("/"), other.path.lstrip("/")
        elif isinstance(other, str):
            a, b = self.path.rstrip("/"), other.lstrip("/")
        else:
            raise TypeError(f"Can only concatenate str or {self.__class__.__name__} to {self.__class__.__name__}")

        return Path(f"{a}/{b}")

    def __rtruediv__(self, other: "str | Path") -> "Path":
        if isinstance(other, Path):
            a, b = other.path.rstrip("/"), self.path.lstrip("/")  # pragma: no cover # covered by __truediv__
        elif isinstance(other, str):
            a, b = other.rstrip("/"), self.path.lstrip("/")
        else:
            raise TypeError(f"Can only concatenate str or {self.__class__.__name__} to {self.__class__.__name__}")

        return Path(f"{a}/{b}")

    def __itruediv__(self, other: "str | Path") -> "Path":
        path = self / other
        self.path = path.path
        self._fragments = path._fragments
        self._parameters = path._parameters
        self._regex = path._regex
        self._template = path._template
        self._matcher = path._matcher
        self._param_order = path._param_order

        return self


_URI_UNRESERVED = r"A-Za-z0-9\-._~"
_URI_RESERVED = r":/?#\[\]@!$&'()*+,;="
_URI_PCT_ENCODED = r"%[0-9A-Fa-f]{2}"


def _uri_encode(value: str, *, reserved: bool) -> str:
    """Pct-encode the characters of a value not allowed in a template expansion.

    :param value: Value to encode.
    :param reserved: Whether reserved characters and pct-encoded triplets are allowed, rather than only unreserved ones.
    :return: Encoded value.
    """
    if not reserved:
        return urllib.parse.quote(value, safe="")

    return "".join(
        x if re.fullmatch(_URI_PCT_ENCODED, x) else urllib.parse.quote(x, safe=_URI_RESERVED.replace("\\", ""))
        for x in re.split(f"({_URI_PCT_ENCODED})", value)
    )


@dataclasses.dataclass(frozen=True)
class _URITemplateOperator:
    """Expansion behaviour of an expression operator, as the table in RFC 6570's Appendix A lists it."""

    first: str
    separator: str
    named: bool
    empty: str
    reserved: bool

    @property
    def pattern(self) -> str:
        """Regex matching what an expression with this operator expands to."""
        if self.reserved:
            allowed = f"[{_URI_UNRESERVED}{_URI_RESERVED}]"
        else:
            allowed = f"[{_URI_UNRESERVED}{re.escape(''.join(sorted({self.separator, ',', '='})))}]"

        return f"{re.escape(self.first)}(?:{allowed}|{_URI_PCT_ENCODED})*"


@dataclasses.dataclass(frozen=True)
class _URITemplateVariable:
    name: str
    explode: bool = False
    prefix: int | None = None


@dataclasses.dataclass(frozen=True)
class _URITemplateExpression:
    OPERATORS: t.ClassVar[dict[str, _URITemplateOperator]] = {
        "": _URITemplateOperator(first="", separator=",", named=False, empty="", reserved=False),
        "+": _URITemplateOperator(first="", separator=",", named=False, empty="", reserved=True),
        "#": _URITemplateOperator(first="#", separator=",", named=False, empty="", reserved=True),
        ".": _URITemplateOperator(first=".", separator=".", named=False, empty="", reserved=False),
        "/": _URITemplateOperator(first="/", separator="/", named=False, empty="", reserved=False),
        ";": _URITemplateOperator(first=";", separator=";", named=True, empty="", reserved=False),
        "?": _URITemplateOperator(first="?", separator="&", named=True, empty="=", reserved=False),
        "&": _URITemplateOperator(first="&", separator="&", named=True, empty="=", reserved=False),
    }
    VARIABLE: t.ClassVar[re.Pattern] = re.compile(
        rf"(?P<name>(?:[A-Za-z0-9_]|{_URI_PCT_ENCODED})(?:\.?(?:[A-Za-z0-9_]|{_URI_PCT_ENCODED}))*)"
        r"(?::(?P<prefix>[1-9][0-9]{0,3})|(?P<explode>\*))?"
    )

    operator: _URITemplateOperator
    variables: tuple[_URITemplateVariable, ...]

    @classmethod
    def build(cls, expression: str) -> "_URITemplateExpression":
        """Parse the text between an expression's braces.

        :param expression: Expression text.
        :return: The expression.
        :raises ValueError: If the expression is malformed or uses an operator RFC 6570 reserves.
        """
        if expression and expression[0] in "=,!@|":
            raise ValueError(f"Operator '{expression[0]}' is reserved by RFC 6570")

        operator = expression[0] if expression and expression[0] in cls.OPERATORS else ""

        variables = []
        for spec in expression[len(operator) :].split(","):
            if (match := cls.VARIABLE.fullmatch(spec)) is None:
                raise ValueError(f"Invalid variable '{spec}' in expression '{{{expression}}}'")

            variables.append(
                _URITemplateVariable(
                    name=match.group("name"),
                    explode=match.group("explode") is not None,
                    prefix=int(match.group("prefix")) if match.group("prefix") else None,
                )
            )

        return cls(operator=cls.OPERATORS[operator], variables=tuple(variables))

    def expand(self, values: t.Mapping[str, t.Any]) -> str:
        """Expand the expression with the given values, following RFC 6570's Appendix A.

        :param values: Values of the variables, skipping those that are missing or None.
        :return: Expansion.
        """
        items = [item for variable in self.variables for item in self._expand_variable(variable, values)]
        return f"{self.operator.first}{self.operator.separator.join(items)}" if items else ""

    def _expand_variable(self, variable: _URITemplateVariable, values: t.Mapping[str, t.Any]) -> list[str]:
        op = self.operator
        value = values.get(variable.name)

        if isinstance(value, t.Mapping):
            members = [
                (_uri_encode(str(k), reserved=op.reserved), _uri_encode(str(v), reserved=op.reserved))
                for k, v in value.items()
                if v is not None
            ]
            if not members:
                return []
            if variable.explode:
                return [f"{k}={v}" if v or not op.named else f"{k}{op.empty}" for k, v in members]
            return [self._named(variable.name, ",".join(f"{k},{v}" for k, v in members))]

        if isinstance(value, list | tuple):
            members = [_uri_encode(str(x), reserved=op.reserved) for x in value if x is not None]
            if not members:
                return []
            if variable.explode:
                return [self._named(variable.name, x) for x in members] if op.named else members
            return [self._named(variable.name, ",".join(members))]

        if value is None:
            return []

        value = str(value)
        if variable.prefix is not None:
            units = re.findall(f"{_URI_PCT_ENCODED}|.", value, re.S) if op.reserved else list(value)
            value = "".join(units[: variable.prefix])

        return [self._named(variable.name, _uri_encode(value, reserved=op.reserved))]

    def _named(self, name: str, value: str) -> str:
        if not self.operator.named:
            return value

        return f"{name}={value}" if value else f"{name}{self.operator.empty}"

    def match(
        self, text: str, kinds: t.Mapping[str, type]
    ) -> list[tuple[_URITemplateVariable, str | list[str] | dict[str, str]]] | None:
        """Extract the values of the expression's variables from what it expanded to.

        :param text: Expansion, empty if no variable was defined.
        :param kinds: Kind of value of each variable, as str, list or dict.
        :return: The defined variables with their values, or None if the text cannot be an expansion.
        """
        if not text:
            return []

        body = text[len(self.operator.first) :]
        if self.operator.named:
            return self._match_named(body, kinds)

        pieces = body.split(self.operator.separator)
        result: list[tuple[_URITemplateVariable, str | list[str] | dict[str, str]]] = []
        for i, variable in enumerate(self.variables[: len(pieces)]):
            raw = self.operator.separator.join(pieces[i:]) if i == len(self.variables) - 1 else pieces[i]
            if (value := self._load(variable, raw, kinds[variable.name])) is None:
                return None
            result.append((variable, value))

        return result

    def _match_named(
        self, body: str, kinds: t.Mapping[str, type]
    ) -> list[tuple[_URITemplateVariable, str | list[str] | dict[str, str]]] | None:
        members = [(x.partition("=")[0], x.partition("=")[2]) for x in body.split(self.operator.separator)]
        named = {x.name for x in self.variables if not (x.explode and kinds[x.name] is dict)}
        claimed: set[int] = set()
        result: list[tuple[_URITemplateVariable, str | list[str] | dict[str, str]]] = []

        for variable in self.variables:
            kind = kinds[variable.name]
            if variable.explode and kind is dict:
                indexes = [i for i, (name, _) in enumerate(members) if name not in named]
                if indexes:
                    pairs = (members[i] for i in indexes)
                    result.append((variable, {urllib.parse.unquote(k): urllib.parse.unquote(v) for k, v in pairs}))
            elif variable.explode and kind is list:
                indexes = [i for i, (name, _) in enumerate(members) if name == variable.name]
                if indexes:
                    result.append((variable, [urllib.parse.unquote(members[i][1]) for i in indexes]))
            else:
                indexes = [i for i, (name, _) in enumerate(members) if name == variable.name][:1]
                if indexes:
                    if (value := self._load(variable, members[indexes[0]][1], kind)) is None:
                        return None
                    result.append((variable, value))

            claimed.update(indexes)

        return result if len(claimed) == len(members) else None

    def _load(self, variable: _URITemplateVariable, raw: str, kind: type) -> str | list[str] | dict[str, str] | None:
        if kind is str:
            return urllib.parse.unquote(raw)

        items = raw.split(self.operator.separator if variable.explode and not self.operator.named else ",")
        if kind is list:
            return [urllib.parse.unquote(x) for x in items]

        if variable.explode:
            if not all("=" in x for x in items):
                return None
            pairs = [tuple(x.split("=", 1)) for x in items]
        elif len(items) % 2:
            return None
        else:
            pairs = list(zip(items[::2], items[1::2]))

        return {urllib.parse.unquote(k): urllib.parse.unquote(v) for k, v in pairs}


class URITemplate:
    """URI template as RFC 6570 defines it, up to level 4, which expands values into URIs and matches URIs back.

    RFC 6570 only defines expansion, so matching inverts it under some rules that keep it unambiguous:

    * Each variable's value is a string, unless ``kinds`` names it a list or an associative array (``dict``), and
      exploded variables are lists by default.
    * In an expression whose operator does not name its variables (any other than ``;``, ``?`` and ``&``), a list or
      associative array must be its last variable, and values cannot contain its separator unencoded, which only
      happens with the ``+`` and ``#`` operators.
    * An expression that names its variables holds at most one exploded associative array, which collects every pair
      not named after another of its variables, and a URI carrying pairs the expression does not expect does not match.
    * A variable may appear several times, as long as each appearance agrees with the others, a prefix being the
      start of the full value.

    Templates breaking these rules are refused.

    :param template: URI template, such as ``users://{id}/profile{?fields*}``.
    :param kinds: Kind of value of the variables that are not strings, as ``list`` or ``dict``.
    :raises ValueError: If the template is malformed, or cannot be matched under the rules above.
    """

    EXPRESSION: t.ClassVar[re.Pattern] = re.compile(r"\{([^{}]*)\}")

    def __init__(self, template: str, *, kinds: t.Mapping[str, type] | None = None) -> None:
        self.template = template
        self._parts: list[str | _URITemplateExpression] = []

        position = 0
        for match in [*self.EXPRESSION.finditer(template), None]:
            literal = template[position : match.start() if match else len(template)]
            if "{" in literal or "}" in literal:
                raise ValueError(f"Unbalanced braces in URI template '{template}'")
            if literal:
                self._parts.append(_uri_encode(literal, reserved=True))
            if match:
                self._parts.append(_URITemplateExpression.build(match.group(1)))
                position = match.end()

        expressions = [x for x in self._parts if isinstance(x, _URITemplateExpression)]
        variables = [v for e in expressions for v in e.variables]
        if unknown := set(kinds or {}) - {v.name for v in variables}:
            raise ValueError(f"Unknown variables {sorted(unknown)} in URI template '{template}'")

        self.kinds: dict[str, type] = {
            v.name: (kinds or {}).get(v.name)
            or (list if any(x.explode for x in variables if x.name == v.name) else str)
            for v in variables
        }
        self._check(expressions)
        self._regex = re.compile(
            "".join(
                re.escape(x) if isinstance(x, str) else f"(?P<e{i}>{x.operator.pattern})?"
                for i, x in enumerate(self._parts)
            )
        )

    @property
    def variables(self) -> list[str]:
        """Names of the template's variables, in the order they first appear."""
        return list(self.kinds)

    def _check(self, expressions: list[_URITemplateExpression]) -> None:
        for name, kind in self.kinds.items():
            if kind not in (str, list, dict):
                raise ValueError(f"Variable '{name}' must be a str, list or dict, not {kind!r}")

        for expression in expressions:
            composites = [v for v in expression.variables if self.kinds[v.name] is not str]
            if any(v.prefix is not None for v in composites):
                raise ValueError(f"Prefix modifiers do not apply to lists or dicts, in '{self.template}'")
            if not expression.operator.named and composites and composites != list(expression.variables[-1:]):
                raise ValueError(
                    f"A list or dict must be the only one and the last variable of an expression not naming its "
                    f"variables, in '{self.template}'"
                )
            if sum(v.explode and self.kinds[v.name] is dict for v in expression.variables) > 1:
                raise ValueError(f"An expression holds at most one exploded dict, in '{self.template}'")

    def expand(self, **values: t.Any) -> str:
        """Build a URI by expanding the template's variables.

        :param values: Values of the variables, as strings, lists or mappings, skipping those that are None.
        :return: URI.
        """
        return "".join(x if isinstance(x, str) else x.expand(values) for x in self._parts)

    def match(self, uri: str) -> dict[str, str | list[str] | dict[str, str]] | None:
        """Extract the values of the template's variables from a URI it expands to.

        :param uri: URI to match.
        :return: The values of the variables the URI defines, or None if it does not match.
        """
        if (match := self._regex.fullmatch(uri)) is None:
            return None

        appearances: dict[str, list[tuple[str | list[str] | dict[str, str], int | None]]] = {}
        for i, part in enumerate(self._parts):
            if isinstance(part, str):
                continue

            if (matched := part.match(match.group(f"e{i}") or "", self.kinds)) is None:
                return None

            for variable, value in matched:
                appearances.setdefault(variable.name, []).append((value, variable.prefix))

        values: dict[str, str | list[str] | dict[str, str]] = {}
        for name, found in appearances.items():
            if (value := self._reconcile(found)) is None:
                return None
            values[name] = value

        return values

    @staticmethod
    def _reconcile(
        appearances: list[tuple[str | list[str] | dict[str, str], int | None]],
    ) -> str | list[str] | dict[str, str] | None:
        """Settle the value of a variable from each of its appearances, a prefix being the start of the full value.

        :param appearances: Value of each appearance, along with its prefix length if it has a prefix modifier.
        :return: The value, or None if the appearances disagree.
        """
        full = [v for v, prefix in appearances if prefix is None]
        value = full[0] if full else max((v for v, _ in appearances), key=len)
        for v, prefix in appearances:
            if prefix is None and v != value:
                return None
            if prefix is not None and not (
                isinstance(value, str) and isinstance(v, str) and (value[:prefix] == v if full else value.startswith(v))
            ):
                return None

        return value

    def __hash__(self) -> int:
        return hash(self.template)

    def __eq__(self, other, /) -> bool:
        return isinstance(other, URITemplate) and self.template == other.template or self.template == other

    def __str__(self) -> str:
        return self.template

    def __repr__(self) -> str:
        return f"URITemplate({self.template!r})"


@dataclasses.dataclass(init=False, eq=False)
class Netloc:
    """Parsed network location (``[userinfo@]host[:port]``) with optional wildcard matching.

    Accepts a full netloc string and decomposes it into structured fields.  Matching is delegated
    to a Rust-backed :class:`NetlocMatcher` operating on the ``host`` field only.

    :param netloc: Network location string or another :class:`Netloc`.
    """

    host: str
    port: int | None
    userinfo: str | None

    def __init__(self, netloc: "str | Netloc" = "") -> None:
        if isinstance(netloc, Netloc):
            self.host = netloc.host
            self.port = netloc.port
            self.userinfo = netloc.userinfo
            self._matcher = netloc._matcher
        else:
            self.host, self.port, self.userinfo = self._parse(netloc)
            self._matcher = NetlocMatcher(self.host) if self.host else None

    @staticmethod
    def _parse(netloc: str) -> tuple[str, int | None, str | None]:
        if not netloc:
            return ("", None, None)

        userinfo: str | None = None
        if "@" in netloc:
            userinfo, netloc = netloc.rsplit("@", 1)

        port: int | None = None
        if ":" in netloc:
            host, port_str = netloc.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                host = netloc
        else:
            host = netloc

        return (host, port, userinfo)

    def match(self, host: str) -> bool:
        """Check whether *host* matches this netloc pattern.

        Supports exact match, wildcard subdomain (``*.example.com``), and the catch-all ``*``.

        :param host: Hostname to check (without port).
        :return: ``True`` when the host matches.
        """
        if self._matcher is None:
            return False

        return self._matcher.is_match(host)

    def __bool__(self) -> bool:
        return self.host != ""

    def __hash__(self) -> int:
        return hash((self.host, self.port, self.userinfo))

    def __eq__(self, other, /) -> bool:
        if isinstance(other, Netloc):
            return self.host == other.host and self.port == other.port and self.userinfo == other.userinfo
        if isinstance(other, str):
            return str(self) == other
        return False

    def __str__(self) -> str:
        result = self.host
        if self.port is not None:
            result = f"{result}:{self.port}"
        if self.userinfo is not None:
            result = f"{self.userinfo}@{result}"
        return result

    def __repr__(self) -> str:
        return f"Netloc('{self}')"


@dataclasses.dataclass
class URL:
    scheme: str
    netloc: Netloc
    path: Path
    params: str
    query: str
    fragment: str

    def __init__(self, url: "str | URL" = "", /, **kwargs):
        """URL object.

        :param url: URL string to be parsed.
        :param kwargs: Individual components to replace those parsed from string.
        """
        parsed_url = urllib.parse.urlparse(url)._replace(**kwargs) if isinstance(url, str) else url
        self.scheme = parsed_url.scheme
        self.netloc = Netloc(parsed_url.netloc)
        self.path = Path(parsed_url.path)
        self.params = parsed_url.params
        self.query = parsed_url.query
        self.fragment = parsed_url.fragment

    @classmethod
    def from_scope(cls, scope: t.MutableMapping[str, t.Any]) -> "URL":
        """Build a URL from an ASGI scope dict.

        Prefers the ``host`` header over the ``server`` scope key, matching standard HTTP semantics
        for reverse-proxy environments.

        :param scope: ASGI connection scope.
        :return: Fully-resolved URL.
        """
        scheme = scope.get("scheme", "http")
        path = scope.get("root_path", "") + scope["path"]
        query_string = scope.get("query_string", b"")

        host_header = None
        for key, value in scope.get("headers", []):
            if key == b"host":
                host_header = value.decode("latin-1")
                break

        if host_header is not None:
            netloc = host_header
        elif (server := scope.get("server")) is not None:
            host, port = server
            default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}.get(scheme)
            netloc = host if port == default_port else f"{host}:{port}"
        else:
            return cls(path)

        url = f"{scheme}://{netloc}{path}"
        if query_string:
            url += "?" + (query_string.decode() if isinstance(query_string, bytes) else query_string)

        return cls(url)

    @property
    def components(self) -> dict[str, str | None]:
        """URL components map.

        :return: Components.
        """
        return {
            "scheme": self.scheme,
            "netloc": str(self.netloc),
            "path": str(self.path),
            "params": self.params,
            "query": self.query,
            "fragment": self.fragment,
        }

    @property
    def url(self) -> str:
        """Build URL string.

        :return: URL string.
        """
        return str(urllib.parse.urlunparse(tuple(self.components.values())))

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, value, /) -> bool:
        return isinstance(value, URL) and self.url == value.url or self.url == value

    def __str__(self) -> str:
        return self.url

    def __repr__(self) -> str:
        return f"URL('{self.url}')"
