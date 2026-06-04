import json
import pathlib
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from flama._cli.commands.start import command


class TestCaseCommand:
    @pytest.mark.parametrize(
        ["flavour", "expected_server_keys"],
        [
            pytest.param("simple", {"host", "port"}, id="simple"),
            pytest.param("full", None, id="full"),
        ],
    )
    def test_create_config(
        self,
        runner: CliRunner,
        tmp_path: pathlib.Path,
        flavour: str,
        expected_server_keys: set[str] | None,
    ) -> None:
        config_file = tmp_path / "flama.json"

        result = runner.invoke(command, [str(config_file), "--create-config", flavour])

        assert result.exit_code == 0, result.output
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert "app" in data
        assert "server" in data
        if expected_server_keys is not None:
            assert set(data["server"].keys()) == expected_server_keys
        else:
            assert len(data["server"]) > 2

    def test_load_and_run(self, runner: CliRunner, tmp_path: pathlib.Path) -> None:
        config_file = tmp_path / "flama.json"
        config_file.touch()

        with patch("flama._cli.commands.start.Config") as config_cls:
            config_instance = MagicMock()
            config_cls.load.return_value = config_instance
            result = runner.invoke(command, [str(config_file)])

        assert result.exit_code == 0, result.output
        assert config_cls.load.call_count == 1
        assert config_instance.run.call_args_list == [call()]
