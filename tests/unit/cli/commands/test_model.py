import json
import tempfile
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from flama.cli.commands.model import command


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def model_component():
    component = Mock()
    component.model.inspect.return_value = {"meta": {}, "artifacts": {}}
    component.model.predict.return_value = [0, 1]
    return component


class TestCaseModelStreamCommand:
    @pytest.mark.parametrize(
        ["buffered", "expected_output"],
        [
            pytest.param(False, "[1][2]", id="streaming"),
            pytest.param(True, "[1][2]\n", id="buffered"),
        ],
    )
    def test_stream(self, runner, model_component, buffered, expected_output):
        async def mock_stream(x):
            async for _ in x:
                yield [1]
                yield [2]

        model_component.model.stream = mock_stream

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([[0, 0]], f)
            f.flush()

            args = ["dummy.flm", "stream", "-f", f.name]
            if buffered:
                args.append("--buffer")

            with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = model_component
                result = runner.invoke(command, args)

        assert result.exit_code == 0, result.output
        assert result.output == expected_output

    def test_stream_invalid_json(self, runner, model_component):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("not valid json")
            f.flush()

            with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = model_component
                result = runner.invoke(command, ["dummy.flm", "stream", "-f", f.name])

        assert result.exit_code != 0

    def test_stream_output_to_file(self, runner, model_component):
        async def mock_stream(x):
            async for _ in x:
                yield [42]

        model_component.model.stream = mock_stream

        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as input_f,
            tempfile.NamedTemporaryFile(mode="r", suffix=".txt", delete=False) as output_f,
        ):
            json.dump([[0, 0]], input_f)
            input_f.flush()

            with patch("flama.cli.commands.model.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = model_component
                result = runner.invoke(
                    command,
                    ["dummy.flm", "stream", "-f", input_f.name, "-o", output_f.name],
                )

            assert result.exit_code == 0, result.output

            output_f.seek(0)
            content = output_f.read()
            assert "[42]" in content
