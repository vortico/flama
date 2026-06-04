from unittest.mock import call, patch

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
                ["--model", "m.flm"],
                [("m.flm", "/", "model")],
                id="bare_path",
            ),
            pytest.param(
                ["--model", "file=m.flm,url=/m,name=m"],
                [("m.flm", "/m", "m")],
                id="kv_url_and_name",
            ),
            pytest.param(
                ["--model", "file=a.flm,url=/a,name=a", "--model", "b.flm"],
                [("a.flm", "/a", "a"), ("b.flm", "/", "model")],
                id="multiple_mixed_forms",
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
        assert config_cls.call_count == 1
        kwargs = config_cls.call_args.kwargs
        app = kwargs["app"]
        assert isinstance(app, DictApp)
        assert isinstance(kwargs["server"], Uvicorn)
        assert [(m.path, m.url, m.name) for m in app.models] == expected_models
        assert config_cls.return_value.run.call_args_list == [call()]

    def test_command_requires_at_least_one_model(self, runner: CliRunner) -> None:
        result = runner.invoke(command, [])

        assert result.exit_code != 0
        assert "--model" in result.output
