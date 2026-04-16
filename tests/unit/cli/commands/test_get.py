import pathlib
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from flama.cli.commands.get import command


@pytest.fixture
def runner():
    return CliRunner()


class TestCaseGetCommand:
    def test_get_huggingface(self, runner):
        with patch("flama.huggingface.module.HuggingFaceModule.get") as mock_get:
            mock_get.return_value = pathlib.Path("my-org_my-model.flm")

            result = runner.invoke(command, ["my-org/my-model", "--source", "huggingface"])

        assert result.exit_code == 0, result.output
        assert "my-org_my-model.flm" in result.output
        mock_get.assert_called_once_with("my-org/my-model", "my-org_my-model.flm", task=None)

    def test_get_huggingface_with_task(self, runner):
        with patch("flama.huggingface.module.HuggingFaceModule.get") as mock_get:
            mock_get.return_value = pathlib.Path("google_gemma-2-2b.flm")

            result = runner.invoke(
                command,
                ["google/gemma-2-2b", "--source", "huggingface", "--task", "text-generation"],
            )

        assert result.exit_code == 0, result.output
        mock_get.assert_called_once_with("google/gemma-2-2b", "google_gemma-2-2b.flm", task="text-generation")

    def test_get_huggingface_with_output(self, runner):
        with patch("flama.huggingface.module.HuggingFaceModule.get") as mock_get:
            mock_get.return_value = pathlib.Path("/tmp/custom.flm")

            result = runner.invoke(
                command,
                ["my-org/my-model", "--source", "huggingface", "-o", "/tmp/custom.flm"],
            )

        assert result.exit_code == 0, result.output
        mock_get.assert_called_once_with("my-org/my-model", "/tmp/custom.flm", task=None)

    def test_get_missing_source(self, runner):
        result = runner.invoke(command, ["my-org/my-model"])
        assert result.exit_code != 0

    def test_get_invalid_source(self, runner):
        result = runner.invoke(command, ["my-org/my-model", "--source", "unknown"])
        assert result.exit_code != 0
