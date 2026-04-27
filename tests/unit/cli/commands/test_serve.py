from unittest.mock import patch

from click.testing import CliRunner

from flama._cli.commands.serve import command
from flama._cli.config.app import DictApp
from flama._cli.config.uvicorn import Uvicorn


class TestCaseCommand:
    def test_command(self, runner: CliRunner) -> None:
        with patch("flama._cli.commands.serve.Config") as config_cls:
            result = runner.invoke(command, ["my-model.flm"])

        assert result.exit_code == 0, result.output
        config_cls.assert_called_once()
        kwargs = config_cls.call_args.kwargs
        assert isinstance(kwargs["app"], DictApp)
        assert isinstance(kwargs["server"], Uvicorn)
        config_cls.return_value.run.assert_called_once_with()
