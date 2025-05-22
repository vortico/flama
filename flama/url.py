import abc
import dataclasses
import decimal
import enum
import re
import typing as t
import urllib.parse
import uuid

T = t.TypeVar("T", bound=t.Union[int, str, float, decimal.Decimal, uuid.UUID])
FragmentType = t.Literal["constant", "rest", "str", "int", "float", "decimal", "uuid"]

__all__ = ["Path", "URL"]


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
    parameters: t.Optional[dict[str, t.Any]]
    matched: t.Optional[str]
    unmatched: t.Optional[str]


@dataclasses.dataclass
class _BuildResult:
    path: str
    unused: dict[str, t.Any]


class Path:
    Match = _Match

    def __init__(self, path: t.Union[str, "Path"]):
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

    @property
    def parameters(self) -> dict[str, type]:
        return {f.name: f.serializer.type for f in self._parameters.values()}

    def match(self, path: t.Union[str, "Path"]) -> _MatchResult:
        """Check if given path matches with current object.

        :param path: Path to match
        :return: Matching result, parameters serialized values and matching parts of the path.
        """
        if (match := self._regex.match(str(path))) is None:
            return _MatchResult(self.Match.none, None, None, None)

        return _MatchResult(
            match=self.Match.partial if match.group("__unmatched__") else self.Match.exact,
            parameters={
                k: self._parameters[k].serializer.load(v)
                for k, v in match.groupdict().items()
                if k not in ("__matched__", "__unmatched__")
            },
            matched=match.group("__matched__") or None,
            unmatched=match.group("__unmatched__") or None,
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

    def __truediv__(self, other: t.Union["Path", str]) -> "Path":
        if isinstance(other, Path):
            a, b = self.path.rstrip("/"), other.path.lstrip("/")
        elif isinstance(other, str):
            a, b = self.path.rstrip("/"), other.lstrip("/")
        else:
            raise TypeError(f"Can only concatenate str or {self.__class__.__name__} to {self.__class__.__name__}")

        return Path(f"{a}/{b}")

    def __rtruediv__(self, other: t.Union["Path", str]) -> "Path":
        if isinstance(other, Path):
            a, b = other.path.rstrip("/"), self.path.lstrip("/")  # pragma: no cover # covered by __truediv__
        elif isinstance(other, str):
            a, b = other.rstrip("/"), self.path.lstrip("/")
        else:
            raise TypeError(f"Can only concatenate str or {self.__class__.__name__} to {self.__class__.__name__}")

        return Path(f"{a}/{b}")

    def __itruediv__(self, other: t.Union["Path", str]) -> "Path":
        path = self / other
        self.path = path.path
        self._fragments = path._fragments
        self._parameters = path._parameters
        self._regex = path._regex
        self._template = path._template

        return self


@dataclasses.dataclass
class URL:
    scheme: str
    netloc: str
    path: Path
    params: str
    query: str
    fragment: str

    def __init__(self, url: t.Union[str, "URL"] = "", /, **kwargs):
        """URL object.

        :param url: URL string to be parsed.
        :param kwargs: Individual components to replace those parsed from string.
        """
        parsed_url = urllib.parse.urlparse(url)._replace(**kwargs) if isinstance(url, str) else url
        self.scheme = parsed_url.scheme
        self.netloc = parsed_url.netloc
        self.path = Path(parsed_url.path)
        self.params = parsed_url.params
        self.query = parsed_url.query
        self.fragment = parsed_url.fragment

    @property
    def components(self) -> dict[str, t.Optional[str]]:
        """URL components map.

        :return: Components.
        """
        return {
            "scheme": self.scheme,
            "netloc": self.netloc,
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
