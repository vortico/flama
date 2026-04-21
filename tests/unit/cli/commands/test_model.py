import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from flama.cli.commands.model import command
from flama.models.base import BaseLLMModel, BaseMLModel


@pytest.fixture
def runner():
    return CliRunner()


def _make_ml_component():
    component = MagicMock()
    component.model = MagicMock(spec=BaseMLModel)
    component.model.inspect.return_value = {"meta": {}, "artifacts": {}}
    component.model.predict.return_value = [0, 1]
    return component


class TestCaseModelInspectCommand:
    def test_inspect(self, runner):
        component = _make_ml_component()

        with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "inspect"])

        assert result.exit_code == 0, result.output

    def test_inspect_pretty(self, runner):
        component = _make_ml_component()

        with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "inspect", "--pretty"])

        assert result.exit_code == 0, result.output


class TestCaseModelPredictCommand:
    def test_predict(self, runner):
        component = _make_ml_component()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([[0, 0]], f)
            f.flush()

            with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = component
                result = runner.invoke(command, ["dummy.flm", "predict", "-f", f.name])

        assert result.exit_code == 0, result.output

    def test_predict_wrong_model_type(self, runner):
        component = MagicMock()
        component.model = MagicMock(spec=BaseLLMModel)
        component.model.inspect.return_value = {"meta": {}, "artifacts": {}}

        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f,
            patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder,
        ):
            json.dump([[0, 0]], f)
            f.flush()
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "predict", "-f", f.name])

        assert result.exit_code != 0
        assert "ML" in result.output


class TestCaseModelStreamCommand:
    @pytest.mark.parametrize(
        ["buffered", "expected_output"],
        [
            pytest.param(False, "[1][2]", id="streaming"),
            pytest.param(True, "[1][2]\n", id="buffered"),
        ],
    )
    def test_stream(self, runner, buffered, expected_output):
        component = _make_ml_component()

        async def mock_stream(x):
            async for _ in x:
                yield [1]
                yield [2]

        component.model.stream = mock_stream

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([[0, 0]], f)
            f.flush()

            args = ["dummy.flm", "stream", "-f", f.name]
            if buffered:
                args.append("--buffer")

            with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = component
                result = runner.invoke(command, args)

        assert result.exit_code == 0, result.output
        assert result.output == expected_output

    def test_stream_invalid_json(self, runner):
        component = _make_ml_component()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("not valid json")
            f.flush()

            with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = component
                result = runner.invoke(command, ["dummy.flm", "stream", "-f", f.name])

        assert result.exit_code != 0

    def test_stream_output_to_file(self, runner):
        component = _make_ml_component()

        async def mock_stream(x):
            async for _ in x:
                yield [42]

        component.model.stream = mock_stream

        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as input_f,
            tempfile.NamedTemporaryFile(mode="r", suffix=".txt", delete=False) as output_f,
        ):
            json.dump([[0, 0]], input_f)
            input_f.flush()

            with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = component
                result = runner.invoke(
                    command,
                    ["dummy.flm", "stream", "-f", input_f.name, "-o", output_f.name],
                )

            assert result.exit_code == 0, result.output

            output_f.seek(0)
            content = output_f.read()
            assert "[42]" in content

    def test_stream_wrong_model_type(self, runner):
        component = MagicMock()
        component.model = MagicMock(spec=BaseLLMModel)
        component.model.inspect.return_value = {"meta": {}, "artifacts": {}}

        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f,
            patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder,
        ):
            json.dump([[0, 0]], f)
            f.flush()
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "stream", "-f", f.name])

        assert result.exit_code != 0
        assert "ML" in result.output
