import tempfile
import typing as t
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from flama.cli.commands.llm import command
from flama.models.base import BaseLLMModel, BaseMLModel


@pytest.fixture(scope="function")
def runner():
    return CliRunner()


def _make_llm_component() -> MagicMock:
    component = MagicMock()
    component.model = MagicMock(spec=BaseLLMModel)
    component.model.inspect.return_value = {"meta": {}, "artifacts": {}}

    async def _mock_query(prompt, **params):
        return "Hello world"

    component.model.query = _mock_query
    component.model.params = {}
    return component


class TestCaseLLMInspectCommand:
    def test_inspect(self, runner):
        component = _make_llm_component()

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "inspect"])

        assert result.exit_code == 0, result.output

    def test_inspect_pretty(self, runner):
        component = _make_llm_component()

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "inspect", "--pretty"])

        assert result.exit_code == 0, result.output


class TestCaseLLMConfigureCommand:
    def test_configure(self, runner):
        component = _make_llm_component()

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(
                command,
                ["dummy.flm", "configure", "--param", "temperature=0.7", "--param", "max_tokens=100"],
            )

        assert result.exit_code == 0, result.output
        assert component.model.configure.call_args_list == [call({"temperature": 0.7, "max_tokens": 100})]

    def test_configure_pretty(self, runner):
        component = _make_llm_component()
        component.model.params = {"temperature": 0.7}

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(
                command,
                ["dummy.flm", "configure", "--param", "temperature=0.7", "--pretty"],
            )

        assert result.exit_code == 0, result.output

    def test_configure_wrong_model_type(self, runner):
        component = MagicMock()
        component.model = MagicMock(spec=BaseMLModel)
        component.model.inspect.return_value = {"meta": {}, "artifacts": {}}

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(
                command,
                ["dummy.flm", "configure", "--param", "temperature=0.7"],
            )

        assert result.exit_code != 0
        assert "LLM" in result.output

    def test_configure_invalid_param_format(self, runner):
        component = _make_llm_component()

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(
                command,
                ["dummy.flm", "configure", "--param", "bad-format"],
            )

        assert result.exit_code != 0


class TestCaseLLMQueryCommand:
    def test_query(self, runner):
        component = _make_llm_component()

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "query", "-p", "What is Python?"])

        assert result.exit_code == 0, result.output
        assert "Hello world" in result.output

    def test_query_with_params(self, runner):
        component = _make_llm_component()
        captured: list[tuple[tuple, dict]] = []

        async def _capturing_query(prompt, **params):
            captured.append(((prompt,), params))
            return "Hello world"

        component.model.query = _capturing_query

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(
                command,
                ["dummy.flm", "query", "-p", "hello", "--param", "temperature=0.7"],
            )

        assert result.exit_code == 0, result.output
        assert captured == [(("hello",), {"temperature": 0.7})]

    def test_query_output_to_file(self, runner):
        component = _make_llm_component()

        with tempfile.NamedTemporaryFile(mode="r", suffix=".txt", delete=False) as output_f:
            with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = component
                result = runner.invoke(
                    command,
                    ["dummy.flm", "query", "-p", "hello", "-o", output_f.name],
                )

            assert result.exit_code == 0, result.output

            output_f.seek(0)
            content = output_f.read()
            assert "Hello world" in content

    def test_query_wrong_model_type(self, runner):
        component = MagicMock()
        component.model = MagicMock(spec=BaseMLModel)
        component.model.inspect.return_value = {"meta": {}, "artifacts": {}}

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "query", "-p", "hello"])

        assert result.exit_code != 0
        assert "LLM" in result.output


class TestCaseLLMStreamCommand:
    @pytest.mark.parametrize(
        ["buffered", "expected_output"],
        [
            pytest.param(False, '"Hello"" world"', id="streaming"),
            pytest.param(True, '"Hello"" world"\n', id="buffered"),
        ],
    )
    def test_stream(self, runner, buffered, expected_output):
        component = _make_llm_component()

        async def mock_stream(prompt, **params):
            for token in ["Hello", " world"]:
                yield token

        component.model.stream = mock_stream

        args = ["dummy.flm", "stream", "-p", "test prompt"]
        if buffered:
            args.append("--buffer")

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(command, args)

        assert result.exit_code == 0, result.output
        assert result.output == expected_output

    def test_stream_with_params(self, runner):
        component = _make_llm_component()
        captured_params: dict[str, t.Any] = {}

        async def mock_stream(prompt, **params):
            captured_params.update(params)
            yield "ok"

        component.model.stream = mock_stream

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-p", "hello", "--param", "temperature=0.7", "--param", "max_tokens=100"],
            )

        assert result.exit_code == 0, result.output
        assert captured_params == {"temperature": 0.7, "max_tokens": 100}

    def test_stream_output_to_file(self, runner):
        component = _make_llm_component()

        async def mock_stream(prompt, **params):
            yield "ok"

        component.model.stream = mock_stream

        with tempfile.NamedTemporaryFile(mode="r", suffix=".txt", delete=False) as output_f:
            with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
                mock_builder.load.return_value = component
                result = runner.invoke(
                    command,
                    ["dummy.flm", "stream", "-p", "hello", "-o", output_f.name],
                )

            assert result.exit_code == 0, result.output

            output_f.seek(0)
            content = output_f.read()
            assert '"ok"' in content

    def test_stream_wrong_model_type(self, runner):
        component = MagicMock()
        component.model = MagicMock(spec=BaseMLModel)
        component.model.inspect.return_value = {"meta": {}, "artifacts": {}}

        with patch("flama.cli.commands.llm.ModelComponentBuilder") as mock_builder:
            mock_builder.load.return_value = component
            result = runner.invoke(command, ["dummy.flm", "stream", "-p", "hello"])

        assert result.exit_code != 0
        assert "LLM" in result.output
