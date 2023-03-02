import abc
import contextlib
import dataclasses
import functools
import itertools
import os
import tempfile
import typing as t
from pathlib import Path

import click
import jinja2

if t.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["Model", "App", "options"]

model_decorators = (
    click.argument("model-path", envvar="FLAMA_MODEL_PATH"),
    click.option("--model-url", envvar="MODEL_URL", default="/", show_default=True, help="Route of the model"),
    click.option("--model-name", envvar="MODEL_NAME", default="model", show_default=True, help="Name of the model"),
)

app_decorators = (
    click.option("--app-debug", envvar="APP_DEBUG", default=False, show_default=True, help="Debug mode"),
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
    def __init__(self, app: t.Union[str, "Flama"], path: Path, module: t.Optional[str] = None):
        self._app = app
        self._module = module
        self._path = path

    @property
    def dir(self) -> str:
        return str(self._path)

    @property
    def app(self) -> t.Union[str, "Flama"]:
        return f"{self._module}:{self._app}" if isinstance(self._app, str) else self._app


@dataclasses.dataclass
class Model:
    url: str
    path: str
    name: str


class App(metaclass=abc.ABCMeta):
    @property  # type: ignore
    @abc.abstractmethod
    @contextlib.contextmanager
    def context(self) -> t.Generator[_AppContext, None, None]:
        ...

    @classmethod
    def build(cls, app: t.Union[str, t.Dict[str, t.Any], "Flama"]) -> "App":
        if isinstance(app, str):
            return StrApp(app)

        if isinstance(app, dict):
            return DictApp.from_dict(app)

        return FlamaApp(app)


@dataclasses.dataclass
class FlamaApp(App):
    app: "Flama"

    @property  # type: ignore
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
    models: t.List[Model] = dataclasses.field(
        default_factory=lambda: [Model(url="/model-url/", path="model-path.flm", name="model-name")]
    )

    @classmethod
    def from_dict(cls, data: t.Dict[str, t.Any]) -> "App":
        if "models" in data:
            data["models"] = [Model(**model) for model in data.pop("models")]
        return cls(**data)  # type: ignore[arg-type]

    @property  # type: ignore
    @contextlib.contextmanager
    def context(self) -> t.Generator[_AppContext, None, None]:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".py") as f:
            env = jinja2.Environment(loader=jinja2.PackageLoader("flama", "cli/templates"))
            f.write(env.get_template("app.py.j2").render(**dataclasses.asdict(self)))
            f.flush()
            file_path = Path(f.name)
            yield _AppContext(app="app", path=file_path.parent, module=file_path.stem)


class StrApp(str, App):
    @property  # type: ignore
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
        model_path: str,
        model_url: str,
        model_name: str,
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
                models=[Model(path=model_path, url=model_url, name=model_name)],
            ),
            *args,
            **kwargs,
        )

    return functools.reduce(lambda x, y: y(x), itertools.chain(app_decorators[::-1], model_decorators[::-1]), _inner)
