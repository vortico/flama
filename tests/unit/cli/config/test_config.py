import json
import logging
import pathlib
from unittest.mock import MagicMock, call, patch

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

    @pytest.mark.parametrize(
        ["method"],
        [pytest.param("loads", id="loads"), pytest.param("load", id="load")],
    )
    def test_loading(self, method: str, tmp_path: pathlib.Path) -> None:
        payload = json.dumps({"app": {"title": "X"}, "server": {"host": "1.2.3.4"}})

        if method == "loads":
            c = Config.loads(payload)
        else:
            f = tmp_path / "c.json"
            f.write_text(payload)
            with f.open() as fs:
                c = Config.load(fs)

        assert isinstance(c.app, DictApp)
        assert c.server.host == "1.2.3.4"

    @pytest.mark.parametrize(
        ["method"],
        [pytest.param("dumps", id="dumps"), pytest.param("dump", id="dump")],
    )
    def test_dumping(self, method: str, tmp_path: pathlib.Path) -> None:
        c = Config()

        if method == "dumps":
            assert json.loads(c.dumps())
        else:
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

        # Patch out dictConfig so the real call doesn't leak ``propagate=False`` onto the `flama`
        # logger for the rest of the xdist worker session (it would break `caplog`-based tests that
        # land in the same worker afterwards). The dictConfig call is covered by `test_run_log_config`.
        with (
            patch.object(c.server, "run") as server_run,
            patch("flama._cli.config.config.logging.config.dictConfig"),
        ):
            c.run()

        assert server_run.call_args_list == [call(asgi_app)]
        assert c.server.app_dir is not None

    def test_run_logs_breadcrumbs(self, caplog_flama: pytest.LogCaptureFixture) -> None:
        asgi_app = MagicMock()
        c = Config(app=FlamaApp(app=asgi_app))

        # Patch out dictConfig so it doesn't reset the `flama` logger's handler list mid-test —
        # otherwise the caplog handler attached by `caplog_flama` would be evicted before the
        # breadcrumbs are emitted. The dictConfig call itself is verified by
        # `test_run_applies_log_config_dict` below.
        with (
            patch.object(c.server, "run"),
            patch("flama._cli.config.config.logging.config.dictConfig"),
            caplog_flama.at_level(logging.INFO, logger="flama._cli.config.config"),
        ):
            c.run()

        messages = [r.getMessage() for r in caplog_flama.records if r.name == "flama._cli.config.config"]
        assert any("Booting Flama application" in m for m in messages)
        assert any("Loading application module" in m for m in messages)

    @pytest.mark.parametrize(
        ["log_config", "expects_dictconfig"],
        [
            pytest.param(None, True, id="dict_applies_dictconfig"),
            pytest.param("/etc/log.yaml", False, id="string_skips_dictconfig"),
        ],
    )
    def test_run_log_config(self, log_config: str | None, expects_dictconfig: bool) -> None:
        asgi_app = MagicMock()
        server = Uvicorn(log_config=log_config) if log_config is not None else Uvicorn()
        c = Config(app=FlamaApp(app=asgi_app), server=server)

        with (
            patch.object(c.server, "run"),
            patch("flama._cli.config.config.logging.config.dictConfig") as p_dictconfig,
        ):
            c.run()

        if expects_dictconfig:
            assert p_dictconfig.call_args_list == [call(c.server.log_config)]
        else:
            assert not p_dictconfig.called


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
