import abc
import dataclasses
import re
import typing as t
import urllib.parse
import uuid
from decimal import Decimal


@dataclasses.dataclass
class URL:
    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str

    def __init__(self, url: str = "", **kwargs: str):
        """URL object.

        :param url: URL string to be parsed.
        :param kwargs: Individual components to replace those parsed from string.
        """
        parsed_url: urllib.parse.ParseResult = urllib.parse.urlparse(url)._replace(**kwargs)
        self.scheme = parsed_url.scheme
        self.netloc = parsed_url.netloc
        self.path = parsed_url.path
        self.params = parsed_url.params
        self.query = parsed_url.query
        self.fragment = parsed_url.fragment

    @property
    def components(self) -> t.Dict[str, t.Optional[str]]:
        """URL components map.

        :return: Components.
        """
        return dataclasses.asdict(self)

    @property
    def url(self) -> str:
        """Build URL string.

        :return: URL string.
        """
        return str(urllib.parse.urlunparse(tuple(self.components.values())))


T = t.TypeVar("T", bound=t.Union[int, str, float, Decimal, uuid.UUID])


class ParamSerializer(t.Generic[T], metaclass=abc.ABCMeta):
    regex: t.ClassVar[str] = ""

    @abc.abstractmethod
    def load(self, value: str) -> T:
        ...

    @abc.abstractmethod
    def dump(self, value: T) -> str:
        ...

    def __eq__(self, other):
        return type(other) == type(self)


class StringParamSerializer(ParamSerializer[str]):
    regex = "[^/]+"

    def load(self, value: str) -> str:
        return str(value)

    def dump(self, value: str) -> str:
        return str(value)


class PathParamSerializer(StringParamSerializer):
    regex = ".*"


class IntegerParamSerializer(ParamSerializer[int]):
    regex = "-?[0-9]+"

    def load(self, value: str) -> int:
        return int(value)

    def dump(self, value: int) -> str:
        return str(value)


class FloatParamSerializer(ParamSerializer[float]):
    regex = "-?[0-9]+(.[0-9]+)?"

    def load(self, value: str) -> float:
        return float(value)

    def dump(self, value: float) -> str:
        return f"{value:0.10f}".rstrip("0").rstrip(".")


class DecimalParamSerializer(ParamSerializer[Decimal]):
    regex = "-?[0-9]+(.[0-9]+)?"

    def load(self, value: str) -> Decimal:
        return Decimal(value)

    def dump(self, value: Decimal) -> str:
        return str(value)


class UUIDParamSerializer(ParamSerializer[uuid.UUID]):
    regex = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

    def load(self, value: str) -> uuid.UUID:
        return uuid.UUID(value)

    def dump(self, value: uuid.UUID) -> str:
        return str(value)


class RegexPath:
    PARAM_REGEX: t.ClassVar[re.Pattern] = re.compile(
        r"{(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)(?::(?P<type>[a-zA-Z_][a-zA-Z0-9_]*)?)?}"
    )
    SERIALIZERS: t.ClassVar[t.Dict[str, ParamSerializer]] = {
        "str": StringParamSerializer(),
        "path": PathParamSerializer(),
        "int": IntegerParamSerializer(),
        "float": FloatParamSerializer(),
        "decimal": DecimalParamSerializer(),
        "uuid": UUIDParamSerializer(),
    }

    def __init__(self, path: t.Union[str, "RegexPath"]):
        """URL path with a regex to allow path params as placeholders.

        Given a path string like: "/foo/{bar:str}"
        path:        "/foo/{bar:str}"
        template:    "/foo/{bar}"
        regex:       "^/foo/(?P<bar>[^/]+)$"
        serializers: {"bar": StringParamSerializer()}

        Path params is a special param defined for nesting routes, it will be removed from path and template, so for a
        path like: "/foo{path:path}" the result will be:
        path:        "/foo"
        template:    "/foo"
        regex:       "^/foo(?P<path>.*)$"
        serializers: {"path": PathParamSerializer()}

        :param path: URL path.
        """
        if isinstance(path, RegexPath):
            self.raw_path: str = path.raw_path
            self.path: str = path.path
            self.template: str = path.template
            self.regex: re.Pattern = path.regex
            self.serializers: t.Dict[str, ParamSerializer] = path.serializers
            self.parameters: t.List[str] = path.parameters
        else:
            self.raw_path = path
            self.path = self.PARAM_REGEX.sub(lambda x: x.group(0) if x.group("type") != "path" else "", path)

            assert self.path == "" or self.path.startswith("/"), "Routed paths must start with '/'"

            self.template = self.PARAM_REGEX.sub(
                lambda x: f"{{{x.group('name')}}}" if x.group("type") != "path" else "", path
            )
            regex = self.PARAM_REGEX.sub(
                lambda x: f"(?P<{x.group('name')}>{self._serializer(x.group('type')).regex})", path
            )
            self.regex = re.compile(rf"^{regex}$")
            self.serializers = {
                param_name: self._serializer(param_type) for param_name, param_type in self.PARAM_REGEX.findall(path)
            }
            self.parameters = list(self.serializers.keys())

    def _serializer(self, param_type: t.Optional[str]) -> ParamSerializer:
        try:
            return self.SERIALIZERS[param_type or "str"]
        except KeyError:
            raise ValueError(f"Unknown path param serializer '{param_type}'")

    def match(self, path: str) -> bool:
        """Check if given path matches with current object.

        :param path: Path to match
        :return: True if matches.
        """
        return self.regex.match(path) is not None

    def values(self, path: str) -> t.Dict[str, t.Any]:
        """Get serialized parameters from a matching path.

        :param path: Path to match.
        :return: Path param values.
        """
        match = self.regex.match(path)

        if match is None:
            raise ValueError(f"Path '{path}' does not match.")

        return {k: self.serializers[k].load(v) for k, v in match.groupdict().items()}

    def build(self, **params: t.Any) -> t.Tuple[str, t.Dict[str, t.Any]]:
        """Build a path by completing param placeholders with given values.

        :param params: Param values.
        :return: Built path and unused params.
        """
        if not set(self.serializers.keys()) <= set(params.keys()):
            formatted_params = ", ".join(f"'{x}'" for x in self.serializers.keys())
            raise ValueError(f"Wrong params, expected: {formatted_params}.")

        if not self.serializers:
            return self.template, params

        remaining_params = {k: v for k, v in params.items() if k not in self.serializers}
        values = {k: self.serializers[k].dump(v) for k, v in params.items() if k in self.serializers}
        path = re.sub(
            pattern=r"|".join(rf"{{({x})}}" for x in values.keys()),
            repl=lambda x: values.pop(x.group(1)),
            string=self.template,
        )
        return path, {**values, **remaining_params}

    def __eq__(self, other) -> bool:
        return isinstance(other, RegexPath) and self.path.__eq__(other.path) or self.path.__eq__(other)

    def __str__(self) -> str:
        return self.path.__str__()

    def __repr__(self) -> str:
        return self.path.__repr__()

    def __add__(self, other) -> "RegexPath":
        if isinstance(other, RegexPath):
            return RegexPath(self.path + other.path)
        elif isinstance(other, str):
            return RegexPath(self.path + other)

        raise TypeError("Can only concatenate str or Path to Path")
