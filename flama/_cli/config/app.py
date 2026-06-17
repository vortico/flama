import abc
import contextlib
import dataclasses
import functools
import itertools
import json
import os
import tempfile
import typing as t
from pathlib import Path

import click
import jinja2

from flama import types
from flama.config.loaders import FileLoader, JSONFileLoader, TOMLFileLoader, YAMLFileLoader

__all__ = ["Model", "App", "options"]


def _parse_params(items: t.Iterable[str]) -> dict[str, t.Any]:
    """Parse a sequence of ``key=value`` strings into a dict.

    Values are JSON-decoded when possible so callers get native types (numbers, booleans,
    nested objects); a plain ``key=value`` falls back to the raw string.

    :param items: Iterable of ``key=value`` strings.
    :return: Decoded mapping.
    :raises ValueError: When an entry is missing the ``=`` separator.
    """
    params: dict[str, t.Any] = {}
    for entry in items:
        if "=" not in entry:
            raise ValueError(f"Parameter must be in key=value format: {entry}")
        key, value = entry.split("=", 1)
        try:
            params[key] = json.loads(value)
        except json.JSONDecodeError:
            params[key] = value
    return params


_FILE_LOADERS: t.Final[dict[str, FileLoader]] = {
    ".json": JSONFileLoader(),
    ".yaml": YAMLFileLoader(),
    ".yml": YAMLFileLoader(),
    ".toml": TOMLFileLoader(),
}


class _ModelSpec(click.ParamType):
    """Parser for ``--model``: bare ``PATH`` shorthand, ``key=value`` pairs, or ``@file``.

    Bare form sets ``url=/``, ``name=model``, ``decoder=None``, ``params=None``,
    ``serving=None``. The full form takes any subset of ``file``, ``url``, ``name``,
    ``channel_scanner``, ``tool_scanner``, ``tool_parser``, ``params``, ``serving`` separated by
    commas; ``file`` is required. ``serving`` accepts a colon-separated list of layer names
    (e.g. ``serving=native:openai``) and applies only to LLM artifacts. ``params`` accepts a
    colon-separated list of ``key=value`` pairs (values are JSON-decoded when possible) and
    applies only to LLM artifacts. The ``@file`` form (e.g. ``--model @spec.json``) loads the
    *whole* spec from a JSON / YAML / TOML file; the file's keys mirror the inline keys, with
    ``params`` as an object and ``serving`` as a list.
    """

    name = "model"

    _ALLOWED_KEYS: t.Final[frozenset[str]] = frozenset(
        {"file", "url", "name", "channel_scanner", "tool_scanner", "tool_parser", "params", "serving"}
    )
    _ALLOWED_CHANNEL_SCANNERS: t.Final[tuple[str, ...]] = (*t.get_args(types.LLMEngineChannelScanners), "auto")
    _ALLOWED_TOOL_SCANNERS: t.Final[tuple[str, ...]] = (*t.get_args(types.LLMEngineToolScanners), "auto")
    _ALLOWED_TOOL_PARSERS: t.Final[tuple[str, ...]] = (*t.get_args(types.LLMEngineToolParsers), "auto")
    _ALLOWED_SERVING: t.Final[tuple[str, ...]] = t.get_args(types.LLMServing)
    _DEFAULTS: t.Final[dict[str, t.Any]] = {
        "file": None,
        "url": "/",
        "name": "model",
        "channel_scanner": None,
        "tool_scanner": None,
        "tool_parser": None,
        "params": None,
        "serving": None,
    }

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> "Model":
        if value.startswith("@"):
            parts = self._load_file(value[1:], param, ctx)
        elif "=" not in value:
            parts = {"file": value}
        else:
            parts = self._parse_kv(value, param, ctx)

        self._validate(parts, param, ctx)
        merged = {**self._DEFAULTS, **parts}
        return Model(
            path=merged["file"],
            url=merged["url"],
            name=merged["name"],
            channel_scanner=merged["channel_scanner"],
            tool_scanner=merged["tool_scanner"],
            tool_parser=merged["tool_parser"],
            params=self._normalise_params(merged["params"], param, ctx),
            serving=self._parse_serving(merged["serving"], param, ctx),
        )

    def _load_file(self, path: str, param: click.Parameter | None, ctx: click.Context | None) -> dict[str, t.Any]:
        suffix = Path(path).suffix.lower()
        loader = _FILE_LOADERS.get(suffix)
        if loader is None:
            self.fail(
                f"Unsupported spec file extension {suffix!r}; expected one of {sorted(_FILE_LOADERS)}", param, ctx
            )
        try:
            data = loader.load(path)
        except FileNotFoundError:
            self.fail(f"Spec file not found: {path!r}", param, ctx)
        except (OSError, ValueError) as exc:
            self.fail(f"Cannot load spec file {path!r}: {exc}", param, ctx)
        if not isinstance(data, dict):
            self.fail(f"Spec file {path!r} must decode to a mapping", param, ctx)
        return data

    def _parse_kv(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> dict[str, t.Any]:
        try:
            parts: dict[str, t.Any] = dict(p.split("=", 1) for p in value.split(","))
        except ValueError:
            self.fail(f"Expected comma-separated key=value pairs, got {value!r}", param, ctx)
        return parts

    def _validate(self, parts: dict[str, t.Any], param: click.Parameter | None, ctx: click.Context | None) -> None:
        if unknown := parts.keys() - self._ALLOWED_KEYS:
            self.fail(f"Unknown key(s): {sorted(unknown)}", param, ctx)
        if "file" not in parts:
            self.fail("'file' is required", param, ctx)
        self._validate_decoder_ref(
            parts.get("channel_scanner"), "channel_scanner", self._ALLOWED_CHANNEL_SCANNERS, param, ctx
        )
        self._validate_decoder_ref(parts.get("tool_scanner"), "tool_scanner", self._ALLOWED_TOOL_SCANNERS, param, ctx)
        self._validate_decoder_ref(parts.get("tool_parser"), "tool_parser", self._ALLOWED_TOOL_PARSERS, param, ctx)

    def _validate_decoder_ref(
        self,
        value: t.Any,
        key: str,
        allowed: tuple[str, ...],
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> None:
        """Reject decoder-ref values that are neither known names nor ``pkg.module:Object`` paths."""
        if value is None or value in allowed or (isinstance(value, str) and ":" in value):
            return
        self.fail(
            f"Unknown {key} {value!r}; expected one of {sorted(allowed)} or 'pkg.module:Object'",
            param,
            ctx,
        )

    def _normalise_params(
        self,
        value: t.Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> dict[str, t.Any] | None:
        """Normalise ``params`` into a dict (or ``None``).

        Inline ``params=k1=v1:k2=v2`` arrives as a colon-separated string; ``@file``-loaded
        ``params`` already arrives as a mapping.
        """
        if value is None:
            return None
        if isinstance(value, dict):
            return t.cast("dict[str, t.Any]", value)
        if not isinstance(value, str):
            self.fail(f"'params' must be a mapping or 'k=v:k=v' string, got {type(value).__name__}", param, ctx)
        entries = tuple(p for p in value.split(":") if p)
        if not entries:
            self.fail("'params' requires at least one key=value pair", param, ctx)
        try:
            return _parse_params(entries)
        except ValueError as exc:
            self.fail(str(exc), param, ctx)

    def _parse_serving(
        self,
        value: t.Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> "tuple[types.LLMServing, ...] | None":
        if value is None:
            return None
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            layers = tuple(value)
        elif isinstance(value, str):
            layers = tuple(p for p in value.split(":") if p)
        else:
            self.fail(f"'serving' must be a list or 'a:b' string, got {type(value).__name__}", param, ctx)
        if not layers:
            self.fail("'serving' requires at least one layer name", param, ctx)
        if unknown := set(layers) - set(self._ALLOWED_SERVING):
            self.fail(
                f"Unknown serving layer(s): {sorted(unknown)}; expected {sorted(self._ALLOWED_SERVING)}", param, ctx
            )
        return t.cast("tuple[types.LLMServing, ...]", layers)


model_decorators = (
    click.option(
        "--model",
        "models_specs",
        type=_ModelSpec(),
        multiple=True,
        required=True,
        metavar=(
            "PATH | @SPEC_FILE | file=PATH[,url=URL][,name=NAME][,channel_scanner=CHANNEL_SCANNER]"
            "[,tool_scanner=TOOL_SCANNER][,tool_parser=TOOL_PARSER][,params=KEY=VALUE[:KEY=VALUE...]]"
            "[,serving=LAYER[:LAYER...]]"
        ),
        help=(
            "Add a model. Repeatable. Bare path shorthand: '--model gemma.flm'. "
            "Full form: '--model file=gemma.flm,url=/llm,name=gemma,"
            "channel_scanner=channel,tool_scanner=auto,tool_parser=auto,"
            "params=temperature=0.7:max_tokens=200,serving=native'. "
            "File form (whole spec from JSON/YAML/TOML): '--model @spec.json'. "
            "Defaults: url=/, name=model, "
            "channel_scanner=auto-detect, tool_scanner=auto-detect, tool_parser=auto-detect, "
            "params=none, serving=auto. 'params' applies to LLM artifacts only."
        ),
    ),
)

app_decorators = (
    click.option("--app-debug", envvar="APP_DEBUG", is_flag=True, default=False, show_default=True, help="Debug mode"),
    click.option("--app-title", envvar="APP_TITLE", default="Flama", show_default=True, help="Name of the application"),
    click.option(
        "--app-version", envvar="APP_VERSION", default="0.1.0", show_default=True, help="Version of the application"
    ),
    click.option(
        "--app-description",
        envvar="APP_DESCRIPTION",
        default="Fire up with the flame",
        show_default=True,
        help="Description of the application",
    ),
    click.option(
        "--app-schema",
        envvar="APP_SCHEMA",
        default="/schema/",
        show_default=True,
        help="Route of the application schema",
    ),
    click.option(
        "--app-docs",
        envvar="APP_DOCS",
        default="/docs/",
        show_default=True,
        help="Route of the application documentation",
    ),
)


class _AppContext:
    def __init__(self, app: "str | types.App", path: Path, module: str | None = None):
        self._app = app
        self._module = module
        self._path = path

    @property
    def dir(self) -> str:
        return str(self._path)

    @property
    def app(self) -> "str | types.App":
        return f"{self._module}:{self._app}" if isinstance(self._app, str) else self._app


@dataclasses.dataclass
class Model:
    url: str
    path: str
    name: str
    channel_scanner: str | None = None
    tool_scanner: str | None = None
    tool_parser: str | None = None
    params: dict[str, t.Any] | None = None
    serving: tuple[types.LLMServing, ...] | None = None

    def __post_init__(self) -> None:
        self.channel_scanner = None if self.channel_scanner == "auto" else self.channel_scanner
        self.tool_scanner = None if self.tool_scanner == "auto" else self.tool_scanner
        self.tool_parser = None if self.tool_parser == "auto" else self.tool_parser


class App(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    @contextlib.contextmanager
    def context(self) -> t.Generator[_AppContext, None, None]: ...

    @classmethod
    def build(cls, app: "str | dict[str, t.Any] | types.App") -> "App":
        if isinstance(app, str):
            return StrApp(app)

        if isinstance(app, dict):
            return DictApp.from_dict(app)  # ty: ignore[invalid-argument-type]

        return FlamaApp(app)


@dataclasses.dataclass
class FlamaApp(App):
    app: "types.App"

    @property
    @contextlib.contextmanager
    def context(self) -> t.Generator[_AppContext, None, None]:
        yield _AppContext(app=self.app, path=Path(os.getcwd()))


@dataclasses.dataclass
class DictApp(App):
    debug: bool = False
    title: str = "Flama"
    version: str = "0.1.0"
    description: str = "Fire up with the flame"
    schema: str = "/schema/"
    docs: str = "/docs/"
    models: list[Model] = dataclasses.field(
        default_factory=lambda: [Model(url="/model-url/", path="model-path.flm", name="model-name")]
    )

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "App":
        if "models" in data:
            data["models"] = [Model(**model) for model in data.pop("models")]
        return cls(**data)  # type: ignore[arg-type]

    @property
    @contextlib.contextmanager
    def context(self) -> t.Generator[_AppContext, None, None]:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".py") as f:
            env = jinja2.Environment(loader=jinja2.PackageLoader("flama", "_cli/templates"))
            f.write(env.get_template("app.py.j2").render(**dataclasses.asdict(self)))
            f.flush()
            file_path = Path(f.name)
            yield _AppContext(app="app", path=file_path.parent, module=file_path.stem)


class StrApp(str, App):
    @property
    @contextlib.contextmanager
    def context(self) -> t.Generator[_AppContext, None, None]:
        module, app = self.split(":")
        yield _AppContext(app=app, path=Path(os.getcwd()), module=module)


def options(command: t.Callable) -> t.Callable:
    """Decorate a click command with all App options.

    :param command: Command to be decorated.
    :return: Decorated command.
    """

    @functools.wraps(command)
    def _inner(
        app_debug: bool,
        app_title: str,
        app_version: str,
        app_description: str,
        app_schema: str,
        app_docs: str,
        models_specs: tuple[Model, ...],
        *args,
        **kwargs,
    ):
        command(
            app=DictApp(
                debug=app_debug,
                title=app_title,
                description=app_description,
                version=app_version,
                schema=app_schema,
                docs=app_docs,
                models=list(models_specs),
            ),
            *args,
            **kwargs,
        )

    return functools.reduce(lambda x, y: y(x), itertools.chain(app_decorators[::-1], model_decorators[::-1]), _inner)
