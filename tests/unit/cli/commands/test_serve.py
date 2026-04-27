from unittest.mock import patch

import pytest
from click.testing import CliRunner

from flama._cli.commands.serve import command
from flama._cli.config.app import DictApp
from flama._cli.config.uvicorn import Uvicorn


class TestCaseCommand:
    @pytest.mark.parametrize(
        ["args", "expected_models"],
        [
            pytest.param(
                ["--model", "my-model.flm", "/", "model"],
                [("my-model.flm", "/", "model")],
                id="single",
            ),
            pytest.param(
                ["--model", "m1.flm", "/m1/", "m1", "--model", "m2.flm", "/m2/", "m2"],
                [("m1.flm", "/m1/", "m1"), ("m2.flm", "/m2/", "m2")],
                id="multiple",
            ),
        ],
    )
    def test_command(
        self,
        runner: CliRunner,
        args: list[str],
        expected_models: list[tuple[str, str, str]],
    ) -> None:
        with patch("flama._cli.commands.serve.Config") as config_cls:
            result = runner.invoke(command, args)

        assert result.exit_code == 0, result.output
        config_cls.assert_called_once()
        kwargs = config_cls.call_args.kwargs
        app = kwargs["app"]
        assert isinstance(app, DictApp)
        assert isinstance(kwargs["server"], Uvicorn)
        assert [(m.path, m.url, m.name) for m in app.models] == expected_models
        config_cls.return_value.run.assert_called_once_with()

    def test_command_requires_at_least_one_model(self, runner: CliRunner) -> None:
        result = runner.invoke(command, [])

        assert result.exit_code != 0
        assert "--model" in result.output
