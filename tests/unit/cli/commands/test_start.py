import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from flama._cli.commands.start import command


class TestCaseCommand:
    @pytest.mark.parametrize(
        "scenario",
        [
            pytest.param("create_simple", id="create_simple"),
            pytest.param("create_full", id="create_full"),
            pytest.param("load_and_run", id="load_and_run"),
        ],
    )
    def test_command(self, runner: CliRunner, tmp_path: pathlib.Path, scenario: str) -> None:
        config_file = tmp_path / "flama.json"

        if scenario == "create_simple":
            result = runner.invoke(command, [str(config_file), "--create-config", "simple"])

            assert result.exit_code == 0, result.output
            assert config_file.exists()
            data = json.loads(config_file.read_text())
            assert "app" in data
            assert "server" in data
            assert set(data["server"].keys()) == {"host", "port"}
        elif scenario == "create_full":
            result = runner.invoke(command, [str(config_file), "--create-config", "full"])

            assert result.exit_code == 0, result.output
            assert config_file.exists()
            data = json.loads(config_file.read_text())
            assert "app" in data
            assert "server" in data
            assert len(data["server"]) > 2
        elif scenario == "load_and_run":
            config_file.touch()
            with patch("flama._cli.commands.start.Config") as config_cls:
                config_instance = MagicMock()
                config_cls.load.return_value = config_instance
                result = runner.invoke(command, [str(config_file)])

            assert result.exit_code == 0, result.output
            config_cls.load.assert_called_once()
            config_instance.run.assert_called_once_with()
