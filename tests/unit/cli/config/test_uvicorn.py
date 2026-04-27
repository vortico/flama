from unittest.mock import patch

import click
from click.testing import CliRunner

from flama._cli.config.uvicorn import Uvicorn, options


class TestCaseUvicorn:
    def test_init(self) -> None:
        u = Uvicorn()

        assert u.host == "127.0.0.1"
        assert u.port == 8000
        assert u.reload is False
        assert u.loop == "auto"

    def test_run(self) -> None:
        u = Uvicorn(host="0.0.0.0", port=9000)

        with patch("flama._cli.config.uvicorn.uvicorn.run") as mock_run:
            u.run("myapp:app")

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == "myapp:app"
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 9000


class TestCaseOptions:
    def test_options(self, runner: CliRunner) -> None:
        @click.command()
        @options
        def cmd(uvicorn: Uvicorn) -> None:
            click.echo(f"host={uvicorn.host},port={uvicorn.port},reload={uvicorn.reload}")

        result = runner.invoke(cmd, ["--server-host", "0.0.0.0", "--server-port", "9000", "--server-reload"])

        assert result.exit_code == 0, result.output
        assert "host=0.0.0.0,port=9000,reload=True" in result.output
