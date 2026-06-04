from unittest.mock import call, patch

from click.testing import CliRunner

from flama._cli.commands.run import command
from flama._cli.config.app import StrApp
from flama._cli.config.uvicorn import Uvicorn


class TestCaseCommand:
    def test_command(self, runner: CliRunner) -> None:
        with patch("flama._cli.commands.run.Config") as config_cls:
            result = runner.invoke(command, ["myapp:app"])

        assert result.exit_code == 0, result.output
        assert config_cls.call_count == 1
        kwargs = config_cls.call_args.kwargs
        assert isinstance(kwargs["app"], StrApp)
        assert kwargs["app"] == "myapp:app"
        assert isinstance(kwargs["server"], Uvicorn)
        assert config_cls.return_value.run.call_args_list == [call()]
