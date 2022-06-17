import dataclasses
import io
import json
import typing

import click
import uvicorn

from flama import Flama


@dataclasses.dataclass(frozen=True)
class Model:
    url: str
    path: str
    name: str


@dataclasses.dataclass(frozen=True)
class AppConfig:
    title: str = ""
    version: str = ""
    description: str = ""
    schema: str = "/schema/"
    docs: str = "/docs/"
    redoc: str = "/redoc/"
    models: typing.List[Model] = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, data: typing.Dict[str, typing.Any]) -> "AppConfig":
        return cls(**{**data, "models": [Model(**model) for model in data.pop("models")]})


@dataclasses.dataclass(frozen=True)
class Config:
    dev: bool = False
    app: typing.Union[AppConfig, str] = dataclasses.field(default_factory=AppConfig)

    @classmethod
    def from_dict(cls, data: typing.Dict[str, typing.Any]) -> "Config":
        app = AppConfig.from_dict(data["app"]) if isinstance(data["app"], dict) else data["app"]
        return cls(**{**data, "app": app})

    @classmethod
    def loads(cls, data: str) -> "Config":
        return cls.from_dict(json.loads(data))

    @classmethod
    def load(cls, fs: io.StringIO) -> "Config":
        return cls.loads(fs.read())

    def dumps(self) -> str:
        return json.dumps(dataclasses.asdict(self))

    def dump(self, fs: io.StringIO) -> None:
        fs.write(self.dumps())

    def build_app(self) -> typing.Union[str, Flama]:
        if isinstance(self.app, str):
            return self.app

        app = Flama(
            title=self.app.title,
            version=self.app.version,
            description=self.app.description,
            schema=self.app.schema,
            docs=self.app.docs,
            redoc=self.app.redoc,
            debug=self.dev,
        )

        for model in self.app.models:
            app.models.add_model(model.url, model=model.path, name=model.name)

        return app


@click.command()
@click.argument("flama-config", envvar="FLAMA_CONFIG", default="flama.json")
@click.option("--create-config", is_flag=True, help="Create minimal config file.")
def start(flama_config: str, create_config: bool):
    """
    Starts a Flama Application based on a config file.
    """
    if create_config:
        with open(flama_config, "w") as fs:
            Config().dump(fs)
            return

    with open(flama_config, "r") as fs:
        config = Config.load(fs)

    uvicorn.run(config.build_app(), reload=config.dev)
