import typing as t
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from flama._cli.config.uvicorn import Uvicorn, options


class TestCaseUvicorn:
    def test_init(self) -> None:
        u = Uvicorn()

        assert u.host == "127.0.0.1"
        assert u.port == 8000
        assert u.reload is False
        assert u.loop == "auto"

    @pytest.mark.parametrize(
        ["log_level", "log_config", "expected_flama_level", "expected_log_config_unchanged"],
        [
            pytest.param(None, None, "INFO", False, id="default_keeps_flama_at_info"),
            pytest.param("debug", None, "DEBUG", False, id="lowercase_log_level_normalises_to_upper"),
            pytest.param("INFO", None, "INFO", False, id="uppercase_log_level_passes_through"),
            pytest.param(10, None, 10, False, id="integer_log_level_passes_through"),
            pytest.param("debug", "/path/to/log.yaml", None, True, id="string_log_config_not_mutated"),
        ],
    )
    def test_run(
        self,
        log_level: str | int | None,
        log_config: str | None,
        expected_flama_level: str | int | None,
        expected_log_config_unchanged: bool,
    ) -> None:
        """Cover :meth:`Uvicorn.run` dispatch and the ``log_level`` propagation hook.

        The hook makes ``--server-log-level`` mean "global server log level" as the flag's docstring
        claims: uvicorn's own ``Config.configure_logging`` only applies ``log_level`` to its own
        loggers (``uvicorn.error`` / ``uvicorn.access`` / ``uvicorn.asgi``), so without this we'd
        leave the ``flama`` logger pinned at the ``INFO`` baked into ``LOGGING_CONFIG`` and silently
        drop every DEBUG/TRACE record from Flama modules at the logger filter. The hook only mutates
        dict configs; a string ``log_config`` path is forwarded untouched so users keep full control
        via ``--server-log-config``. String levels are normalised to upper-case to match the dict
        config's existing convention; integers pass through verbatim.
        """
        kwargs: dict[str, t.Any] = {"host": "0.0.0.0", "port": 9000}
        if log_level is not None:
            kwargs["log_level"] = log_level
        if log_config is not None:
            kwargs["log_config"] = log_config

        u = Uvicorn(**kwargs)

        with patch("flama._cli.config.uvicorn.uvicorn.run") as mock_run:
            u.run("myapp:app")

        assert mock_run.call_count == 1
        args, run_kwargs = mock_run.call_args
        assert args[0] == "myapp:app"
        assert run_kwargs["host"] == "0.0.0.0"
        assert run_kwargs["port"] == 9000

        if expected_log_config_unchanged:
            assert u.log_config == log_config
        else:
            assert isinstance(u.log_config, dict)
            assert u.log_config["loggers"]["flama"]["level"] == expected_flama_level

    @pytest.mark.parametrize(
        ["assertion"],
        [
            pytest.param(
                lambda cfg: (
                    {"uvicorn", "uvicorn.error", "uvicorn.access", "flama"} <= set(cfg["loggers"])
                    and cfg["loggers"]["flama"]["handlers"] == ["default"]
                    and cfg["loggers"]["uvicorn"]["handlers"] == ["default"]
                    and cfg["loggers"]["uvicorn.access"]["handlers"] == ["access"]
                ),
                id="includes_uvicorn_and_flama_loggers",
            ),
            pytest.param(
                lambda cfg: all(
                    cfg["handlers"][n]["class"] == "rich.logging.RichHandler"
                    and cfg["handlers"][n]["console"] == "ext://flama._cli.formatting.CONSOLE"
                    for n in ("default", "access")
                ),
                id="handlers_use_rich_handler",
            ),
            pytest.param(
                lambda cfg: all(cfg["formatters"][n]["fmt"].startswith("[%(name)s]") for n in ("default", "access")),
                id="formatters_prefix_logger_name",
            ),
        ],
    )
    def test_log_config(self, assertion) -> None:
        cfg = Uvicorn().log_config

        assert isinstance(cfg, dict)
        assert assertion(cfg)

    def test_log_config_default_factory_returns_independent_copy(self) -> None:
        u1 = Uvicorn()
        u2 = Uvicorn()

        assert u1.log_config == u2.log_config
        assert u1.log_config is not u2.log_config
        assert u1.log_config["handlers"] is not u2.log_config["handlers"]


class TestCaseOptions:
    def test_options(self, runner: CliRunner) -> None:
        @click.command()
        @options
        def cmd(uvicorn: Uvicorn) -> None:
            click.echo(f"host={uvicorn.host},port={uvicorn.port},reload={uvicorn.reload}")

        result = runner.invoke(cmd, ["--server-host", "0.0.0.0", "--server-port", "9000", "--server-reload"])

        assert result.exit_code == 0, result.output
        assert "host=0.0.0.0,port=9000,reload=True" in result.output

    @pytest.mark.parametrize(
        ["explicit_path"],
        [
            pytest.param(False, id="default_factory_includes_flama_logger"),
            pytest.param(True, id="explicit_path_passes_through"),
        ],
    )
    def test_log_config(self, runner: CliRunner, tmp_path, explicit_path: bool) -> None:
        captured: dict[str, Uvicorn] = {}

        @click.command()
        @options
        def cmd(uvicorn: Uvicorn) -> None:
            captured["uvicorn"] = uvicorn

        if explicit_path:
            cfg = tmp_path / "log.yaml"
            cfg.write_text("version: 1\n")
            result = runner.invoke(cmd, ["--server-log-config", str(cfg)])
        else:
            result = runner.invoke(cmd, [])

        assert result.exit_code == 0, result.output
        u = captured["uvicorn"]
        if explicit_path:
            assert u.log_config == str(cfg)
        else:
            assert isinstance(u.log_config, dict)
            assert "flama" in u.log_config["loggers"]
            assert u.log_config["handlers"]["default"]["class"] == "rich.logging.RichHandler"
