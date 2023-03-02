import abc
import dataclasses
import functools
import io
import json
import typing as t

from flama.cli.config.app import App
from flama.cli.config.uvicorn import Uvicorn

__all__ = ["Config", "ExampleConfig", "options"]


@dataclasses.dataclass
class Config:
    app: App = dataclasses.field(
        default_factory=lambda: App.build({"title": "API title", "version": "0.1.0", "description": "API description"})
    )
    server: Uvicorn = dataclasses.field(default_factory=Uvicorn)

    @classmethod
    def from_dict(cls, data: t.Dict[str, t.Any]) -> "Config":
        return cls(
            **{**data, "app": App.build(data["app"]), "server": Uvicorn(**data["server"])}  # type: ignore[arg-type]
        )

    def to_dict(self) -> t.Dict[str, t.Any]:
        return dataclasses.asdict(self)

    @classmethod
    def loads(cls, data: str) -> "Config":
        return cls.from_dict(json.loads(data))

    @classmethod
    def load(cls, fs: io.StringIO) -> "Config":
        return cls.loads(fs.read())

    def dumps(self) -> str:
        return json.dumps(self.to_dict())

    def dump(self, fs: io.StringIO) -> None:
        fs.write(self.dumps())

    @classmethod
    def dump_example(cls, type: str) -> t.Dict[str, t.Any]:
        result = cls().to_dict()
        if type == "simple":
            result["server"] = {k: v for k, v in result["server"] if k in ("host", "port")}
        return result

    def run(self) -> None:
        with self.app.context as app_context:
            self.server.app_dir = app_context.dir
            self.server.run(app_context.app)


class ExampleConfig(metaclass=abc.ABCMeta):
    config = Config()

    @classmethod
    def build(cls, mode: str) -> "ExampleConfig":
        return {"simple": SimpleExample(), "full": FullExample()}[mode]

    @classmethod
    @abc.abstractmethod
    def dumps(cls) -> str:
        ...


class SimpleExample(ExampleConfig):
    @classmethod
    def dumps(cls) -> str:
        return json.dumps(
            {
                **cls.config.to_dict(),
                "server": {k: v for k, v in cls.config.to_dict()["server"].items() if k in ("host", "port")},
            }
        )


class FullExample(ExampleConfig):
    @classmethod
    def dumps(cls):
        return json.dumps(cls.config.to_dict())


def options(command: t.Callable) -> t.Callable:
    """Decorate a click command with all Config options.

    :param command: Command to be decorated.
    :return: Decorated command.
    """

    @functools.wraps(command)
    def _inner(*args, **kwargs):
        command(*args, **kwargs)

    return _inner
