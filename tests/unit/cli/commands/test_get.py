import pathlib
from unittest.mock import call, patch

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
        assert mock_get.call_args_list == [
            call("my-org/my-model", output="my-org_my-model.flm", task=None, engine="transformers")
        ]

    def test_get_huggingface_with_task(self, runner):
        with patch("flama.huggingface.module.HuggingFaceModule.get") as mock_get:
            mock_get.return_value = pathlib.Path("my-org_my-model.flm")

            result = runner.invoke(
                command,
                ["my-org/my-model", "--source", "huggingface", "--task", "text-generation"],
            )

        assert result.exit_code == 0, result.output
        assert mock_get.call_args_list == [
            call("my-org/my-model", output="my-org_my-model.flm", task="text-generation", engine="transformers")
        ]

    def test_get_huggingface_with_output(self, runner):
        with patch("flama.huggingface.module.HuggingFaceModule.get") as mock_get:
            mock_get.return_value = pathlib.Path("/tmp/custom.flm")

            result = runner.invoke(
                command,
                ["my-org/my-model", "--source", "huggingface", "-o", "/tmp/custom.flm"],
            )

        assert result.exit_code == 0, result.output
        assert mock_get.call_args_list == [
            call("my-org/my-model", output="/tmp/custom.flm", task=None, engine="transformers")
        ]

    def test_get_huggingface_with_engine_vllm(self, runner):
        with patch("flama.huggingface.module.HuggingFaceModule.get") as mock_get:
            mock_get.return_value = pathlib.Path("my-org_my-model.flm")

            result = runner.invoke(
                command,
                ["my-org/my-model", "--source", "huggingface", "--engine", "vllm"],
            )

        assert result.exit_code == 0, result.output
        assert mock_get.call_args_list == [
            call("my-org/my-model", output="my-org_my-model.flm", task=None, engine="vllm")
        ]

    def test_get_missing_source(self, runner):
        result = runner.invoke(command, ["my-org/my-model"])
        assert result.exit_code != 0

    def test_get_invalid_source(self, runner):
        result = runner.invoke(command, ["my-org/my-model", "--source", "unknown"])
        assert result.exit_code != 0
