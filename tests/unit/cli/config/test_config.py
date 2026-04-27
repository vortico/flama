import json
import pathlib
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from flama._cli.config.app import App, DictApp, FlamaApp
from flama._cli.config.config import Config, ExampleConfig, FullExample, SimpleExample, options
from flama._cli.config.uvicorn import Uvicorn


class TestCaseConfig:
    def test_init(self) -> None:
        c = Config()

        assert isinstance(c.app, App)
        assert isinstance(c.server, Uvicorn)

    def test_from_dict(self) -> None:
        data = {"app": {"title": "X"}, "server": {"host": "1.2.3.4"}}

        c = Config.from_dict(data)

        assert isinstance(c.app, DictApp)
        assert c.app.title == "X"
        assert c.server.host == "1.2.3.4"

    def test_to_dict(self) -> None:
        c = Config()

        result = c.to_dict()

        assert "app" in result
        assert "server" in result

    def test_loads(self) -> None:
        s = json.dumps({"app": {"title": "X"}, "server": {"host": "1.2.3.4"}})

        c = Config.loads(s)

        assert isinstance(c.app, DictApp)
        assert c.server.host == "1.2.3.4"

    def test_load(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "c.json"
        f.write_text(json.dumps({"app": {"title": "X"}, "server": {"host": "1.2.3.4"}}))

        with f.open() as fs:
            c = Config.load(fs)

        assert c.server.host == "1.2.3.4"

    def test_dumps(self) -> None:
        c = Config()

        result = c.dumps()

        assert json.loads(result)

    def test_dump(self, tmp_path: pathlib.Path) -> None:
        c = Config()
        f = tmp_path / "c.json"

        with f.open("w") as fs:
            c.dump(fs)

        assert json.loads(f.read_text())

    @pytest.mark.parametrize(
        ["mode", "expected_server_keys"],
        [
            pytest.param("simple", {"host", "port"}, id="simple"),
            pytest.param("full", None, id="full"),
        ],
    )
    def test_dump_example(self, mode: str, expected_server_keys: set[str] | None) -> None:
        result = Config.dump_example(mode)

        assert "app" in result
        assert "server" in result
        if expected_server_keys is not None:
            assert set(result["server"].keys()) == expected_server_keys

    def test_run(self) -> None:
        asgi_app = MagicMock()
        c = Config(app=FlamaApp(app=asgi_app))

        with patch.object(c.server, "run") as server_run:
            c.run()

        server_run.assert_called_once_with(asgi_app)
        assert c.server.app_dir is not None


class TestCaseExampleConfig:
    @pytest.mark.parametrize(
        ["mode", "expected_class"],
        [
            pytest.param("simple", SimpleExample, id="simple"),
            pytest.param("full", FullExample, id="full"),
        ],
    )
    def test_build(self, mode: str, expected_class: type[ExampleConfig]) -> None:
        result = ExampleConfig.build(mode)

        assert isinstance(result, expected_class)


class TestCaseSimpleExample:
    def test_dumps(self) -> None:
        result = SimpleExample.dumps()

        data = json.loads(result)
        assert "app" in data
        assert "server" in data
        assert set(data["server"].keys()) == {"host", "port"}


class TestCaseFullExample:
    def test_dumps(self) -> None:
        result = FullExample.dumps()

        data = json.loads(result)
        assert "app" in data
        assert "server" in data
        assert len(data["server"]) > 2


class TestCaseOptions:
    def test_options(self, runner: CliRunner) -> None:
        @click.command()
        @options
        def cmd() -> None:
            click.echo("ok")

        result = runner.invoke(cmd, [])

        assert result.exit_code == 0, result.output
        assert "ok" in result.output
