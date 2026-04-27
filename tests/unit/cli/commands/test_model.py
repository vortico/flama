import json
import pathlib
import typing as t
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from flama._cli.commands.model import command
from flama.models.base import BaseLLMModel, BaseMLModel


class TestCaseCommand:
    @pytest.mark.parametrize(
        "scenario",
        [
            pytest.param("normal_load", id="normal_load"),
            pytest.param("file_not_found", id="file_not_found"),
        ],
    )
    def test_command(
        self,
        runner: CliRunner,
        ml_component: MagicMock,
        scenario: str,
    ) -> None:
        with patch("flama._cli.commands.model.MLModelComponentBuilder") as builder:
            if scenario == "normal_load":
                builder.load.return_value = ml_component
                result = runner.invoke(command, ["dummy.flm", "inspect"])

                assert result.exit_code == 0, result.output
                builder.load.assert_called_once_with("dummy.flm")
            elif scenario == "file_not_found":
                builder.load.side_effect = FileNotFoundError("no")
                result = runner.invoke(command, ["missing.flm", "inspect"])

                assert result.exit_code != 0
                assert "Model file not found" in result.output


class TestCaseInspect:
    @pytest.mark.parametrize(
        "scenario",
        [
            pytest.param("default", id="default"),
            pytest.param("pretty", id="pretty"),
        ],
    )
    def test_inspect(
        self,
        runner: CliRunner,
        ml_component: MagicMock,
        patched_ml_builder: MagicMock,
        scenario: str,
    ) -> None:
        args = ["dummy.flm", "inspect"]
        if scenario == "pretty":
            args.append("--pretty")

        result = runner.invoke(command, args)

        assert result.exit_code == 0, result.output
        ml_component.model.inspect.assert_called_once()


class TestCasePredict:
    @pytest.fixture(scope="function")
    def input_file(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "in.json"
        path.write_text(json.dumps([[0, 0]]))
        return path

    @pytest.mark.parametrize(
        ["ml_component", "scenario"],
        [
            pytest.param(BaseMLModel, "default", id="default"),
            pytest.param(BaseLLMModel, "wrong_type", id="wrong_type"),
        ],
        indirect=["ml_component"],
    )
    def test_predict(
        self,
        runner: CliRunner,
        ml_component: MagicMock,
        patched_ml_builder: MagicMock,
        input_file: pathlib.Path,
        scenario: str,
    ) -> None:
        if scenario == "default":
            result = runner.invoke(command, ["dummy.flm", "predict", "-f", str(input_file)])

            assert result.exit_code == 0, result.output
            ml_component.model.predict.assert_called_once_with([[0, 0]])
        elif scenario == "wrong_type":
            result = runner.invoke(command, ["dummy.flm", "predict", "-f", str(input_file)])

            assert result.exit_code != 0
            assert "ML" in result.output


class TestCaseStream:
    @pytest.fixture(scope="function")
    def input_file(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "in.json"
        path.write_text(json.dumps([[0, 0]]))
        return path

    @pytest.mark.parametrize(
        ["ml_component", "scenario", "expected_output"],
        [
            pytest.param(BaseMLModel, "streaming", "[1][2]", id="streaming"),
            pytest.param(BaseMLModel, "buffered", "[1][2]\n", id="buffered"),
            pytest.param(BaseMLModel, "invalid_json", None, id="invalid_json"),
            pytest.param(BaseMLModel, "output_to_file", None, id="output_to_file"),
            pytest.param(BaseLLMModel, "wrong_type", None, id="wrong_type"),
        ],
        indirect=["ml_component"],
    )
    def test_stream(
        self,
        runner: CliRunner,
        ml_component: MagicMock,
        patched_ml_builder: MagicMock,
        input_file: pathlib.Path,
        tmp_path: pathlib.Path,
        scenario: str,
        expected_output: str | None,
    ) -> None:
        async def _stream(x: t.AsyncIterator[t.Any]) -> t.AsyncIterator[list[int]]:
            async for _ in x:
                yield [1]
                yield [2]

        ml_component.model.stream = _stream

        if scenario == "streaming":
            result = runner.invoke(command, ["dummy.flm", "stream", "-f", str(input_file)])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "buffered":
            result = runner.invoke(command, ["dummy.flm", "stream", "-f", str(input_file), "--buffer"])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "invalid_json":
            bad_input = tmp_path / "bad.txt"
            bad_input.write_text("not valid json")
            result = runner.invoke(command, ["dummy.flm", "stream", "-f", str(bad_input)])

            assert result.exit_code != 0
        elif scenario == "output_to_file":

            async def _short_stream(x: t.AsyncIterator[t.Any]) -> t.AsyncIterator[list[int]]:
                async for _ in x:
                    yield [42]

            ml_component.model.stream = _short_stream
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-f", str(input_file), "-o", str(output)],
            )

            assert result.exit_code == 0, result.output
            assert "[42]" in output.read_text()
        elif scenario == "wrong_type":
            result = runner.invoke(command, ["dummy.flm", "stream", "-f", str(input_file)])

            assert result.exit_code != 0
            assert "ML" in result.output
