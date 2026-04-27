import json
import pathlib
import typing as t
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from flama._cli.commands.model import _parse_params, _read_input, command
from flama.concurrency import iterate
from flama.models.base import BaseLLMModel, BaseMLModel


async def _ml_stream_two_items(
    x: t.AsyncIterable[t.Iterable[t.Any]] | t.Iterable[t.Iterable[t.Any]],
) -> t.AsyncIterator[list[int]]:
    async for _ in iterate(x):
        yield [1]
        yield [2]


async def _ml_stream_one_item(
    x: t.AsyncIterable[t.Iterable[t.Any]] | t.Iterable[t.Iterable[t.Any]],
) -> t.AsyncIterator[list[int]]:
    async for _ in iterate(x):
        yield [42]


async def _llm_stream_two_tokens(prompt: str, **params: t.Any) -> t.AsyncIterator[str]:
    for token in ["Hello", " world"]:
        yield token


async def _llm_stream_one_token(prompt: str, **params: t.Any) -> t.AsyncIterator[str]:
    yield "ok"


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
        with patch("flama._cli.commands.model.ModelComponentBuilder") as builder:
            if scenario == "normal_load":
                builder.build.return_value = ml_component
                result = runner.invoke(command, ["dummy.flm", "inspect"])

                assert result.exit_code == 0, result.output
                builder.build.assert_called_once_with("dummy.flm")
            elif scenario == "file_not_found":
                builder.build.side_effect = FileNotFoundError("no")
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
    @pytest.mark.parametrize(
        ["builder_fixture", "component_fixture"],
        [
            pytest.param("patched_ml_builder", "ml_component", id="ml"),
            pytest.param("patched_llm_builder", "llm_component", id="llm"),
        ],
    )
    def test_inspect(
        self,
        runner: CliRunner,
        request: pytest.FixtureRequest,
        builder_fixture: str,
        component_fixture: str,
        scenario: str,
    ) -> None:
        request.getfixturevalue(builder_fixture)
        component: MagicMock = request.getfixturevalue(component_fixture)

        args = ["dummy.flm", "inspect"]
        if scenario == "pretty":
            args.append("--pretty")

        result = runner.invoke(command, args)

        assert result.exit_code == 0, result.output
        component.model.inspect.assert_called_once()


class TestCaseRun:
    @pytest.fixture(scope="function")
    def input_file(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "in.json"
        path.write_text(json.dumps([[0, 0]]))
        return path

    @pytest.mark.parametrize(
        ["ml_component", "scenario"],
        [
            pytest.param(BaseMLModel, "via_file", id="via_file"),
            pytest.param(BaseMLModel, "via_input", id="via_input"),
            pytest.param(BaseMLModel, "via_stdin", id="via_stdin"),
            pytest.param(BaseMLModel, "invalid_json", id="invalid_json"),
            pytest.param(BaseMLModel, "with_param_rejected", id="with_param_rejected"),
        ],
        indirect=["ml_component"],
    )
    def test_run_ml(
        self,
        runner: CliRunner,
        ml_component: MagicMock,
        patched_ml_builder: MagicMock,
        input_file: pathlib.Path,
        scenario: str,
    ) -> None:
        if scenario == "via_file":
            result = runner.invoke(command, ["dummy.flm", "run", "-f", str(input_file)])

            assert result.exit_code == 0, result.output
            ml_component.model.predict.assert_called_once_with([[0, 0]])
        elif scenario == "via_input":
            result = runner.invoke(command, ["dummy.flm", "run", "-i", "[[1, 2]]"])

            assert result.exit_code == 0, result.output
            ml_component.model.predict.assert_called_once_with([[1, 2]])
        elif scenario == "via_stdin":
            result = runner.invoke(command, ["dummy.flm", "run"], input="[[3, 4]]")

            assert result.exit_code == 0, result.output
            ml_component.model.predict.assert_called_once_with([[3, 4]])
        elif scenario == "invalid_json":
            result = runner.invoke(command, ["dummy.flm", "run", "-i", "not json"])

            assert result.exit_code != 0
            assert "valid JSON" in result.output
        elif scenario == "with_param_rejected":
            result = runner.invoke(
                command,
                ["dummy.flm", "run", "-i", "[[0]]", "--param", "temperature=0.7"],
            )

            assert result.exit_code != 0
            assert "--param" in result.output

    @pytest.mark.parametrize(
        ["llm_component", "scenario"],
        [
            pytest.param(BaseLLMModel, "via_input", id="via_input"),
            pytest.param(BaseLLMModel, "via_file", id="via_file"),
            pytest.param(BaseLLMModel, "via_stdin", id="via_stdin"),
            pytest.param(BaseLLMModel, "with_params", id="with_params"),
            pytest.param(BaseLLMModel, "output_to_file", id="output_to_file"),
            pytest.param(BaseLLMModel, "pretty", id="pretty"),
            pytest.param(BaseLLMModel, "mutually_exclusive", id="mutually_exclusive"),
        ],
        indirect=["llm_component"],
    )
    def test_run_llm(
        self,
        runner: CliRunner,
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        tmp_path: pathlib.Path,
        scenario: str,
    ) -> None:
        if scenario == "via_input":
            result = runner.invoke(command, ["dummy.flm", "run", "-i", "What is Python?"])

            assert result.exit_code == 0, result.output
            assert "Hello world" in result.output
        elif scenario == "via_file":
            prompt = tmp_path / "prompt.txt"
            prompt.write_text("What is Python?")
            result = runner.invoke(command, ["dummy.flm", "run", "-f", str(prompt)])

            assert result.exit_code == 0, result.output
            assert "Hello world" in result.output
        elif scenario == "via_stdin":
            result = runner.invoke(command, ["dummy.flm", "run"], input="What is Python?")

            assert result.exit_code == 0, result.output
            assert "Hello world" in result.output
        elif scenario == "with_params":
            captured: dict[str, t.Any] = {}

            async def _capturing_query(prompt: str, **params: t.Any) -> str:
                captured.update(params)
                return "Hello world"

            llm_component.model.query = _capturing_query
            result = runner.invoke(
                command,
                ["dummy.flm", "run", "-i", "hello", "--param", "temperature=0.7", "--param", "max_tokens=100"],
            )

            assert result.exit_code == 0, result.output
            assert captured == {"temperature": 0.7, "max_tokens": 100}
        elif scenario == "output_to_file":
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "run", "-i", "hello", "-o", str(output)],
            )

            assert result.exit_code == 0, result.output
            assert "Hello world" in output.read_text()
        elif scenario == "pretty":
            result = runner.invoke(command, ["dummy.flm", "run", "-i", "hello", "--pretty"])

            assert result.exit_code == 0, result.output
        elif scenario == "mutually_exclusive":
            anything = tmp_path / "anything.txt"
            anything.write_text("x")
            result = runner.invoke(
                command,
                ["dummy.flm", "run", "-i", "hello", "-f", str(anything)],
            )

            assert result.exit_code != 0


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
            pytest.param(BaseMLModel, "with_param_rejected", None, id="with_param_rejected"),
        ],
        indirect=["ml_component"],
    )
    def test_stream_ml(
        self,
        runner: CliRunner,
        ml_component: MagicMock,
        patched_ml_builder: MagicMock,
        input_file: pathlib.Path,
        tmp_path: pathlib.Path,
        scenario: str,
        expected_output: str | None,
    ) -> None:
        ml_component.model.stream = _ml_stream_two_items

        if scenario == "streaming":
            result = runner.invoke(command, ["dummy.flm", "stream", "-f", str(input_file)])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "buffered":
            result = runner.invoke(command, ["dummy.flm", "stream", "-f", str(input_file), "--buffer"])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "invalid_json":
            result = runner.invoke(command, ["dummy.flm", "stream", "-i", "not json"])

            assert result.exit_code != 0
            assert "valid JSON" in result.output
        elif scenario == "output_to_file":
            ml_component.model.stream = _ml_stream_one_item
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-f", str(input_file), "-o", str(output)],
            )

            assert result.exit_code == 0, result.output
            assert "[42]" in output.read_text()
        elif scenario == "with_param_rejected":
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-i", "[[0]]", "--param", "temperature=0.7"],
            )

            assert result.exit_code != 0
            assert "--param" in result.output

    @pytest.mark.parametrize(
        ["llm_component", "scenario", "expected_output"],
        [
            pytest.param(BaseLLMModel, "streaming", '"Hello"" world"', id="streaming"),
            pytest.param(BaseLLMModel, "buffered", '"Hello"" world"\n', id="buffered"),
            pytest.param(BaseLLMModel, "with_params", None, id="with_params"),
            pytest.param(BaseLLMModel, "output_to_file", None, id="output_to_file"),
        ],
        indirect=["llm_component"],
    )
    def test_stream_llm(
        self,
        runner: CliRunner,
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        tmp_path: pathlib.Path,
        scenario: str,
        expected_output: str | None,
    ) -> None:
        llm_component.model.stream = _llm_stream_two_tokens

        if scenario == "streaming":
            result = runner.invoke(command, ["dummy.flm", "stream", "-i", "test"])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "buffered":
            result = runner.invoke(command, ["dummy.flm", "stream", "-i", "test", "--buffer"])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "with_params":
            captured: dict[str, t.Any] = {}

            async def _capturing_stream(prompt: str, **params: t.Any) -> t.AsyncIterator[str]:
                captured.update(params)
                yield "ok"

            llm_component.model.stream = _capturing_stream
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-i", "hello", "--param", "temperature=0.7", "--param", "max_tokens=100"],
            )

            assert result.exit_code == 0, result.output
            assert captured == {"temperature": 0.7, "max_tokens": 100}
        elif scenario == "output_to_file":
            llm_component.model.stream = _llm_stream_one_token
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-i", "hello", "-o", str(output)],
            )

            assert result.exit_code == 0, result.output
            assert '"ok"' in output.read_text()


class TestCaseReadInput:
    @pytest.mark.parametrize(
        ["scenario"],
        [
            pytest.param("input_str", id="input_str"),
            pytest.param("input_file", id="input_file"),
            pytest.param("stdin", id="stdin"),
            pytest.param("both_provided", id="both_provided"),
        ],
    )
    def test__read_input(self, scenario: str, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        if scenario == "input_str":
            assert _read_input("hello", None) == "hello"
        elif scenario == "input_file":
            file = tmp_path / "in.txt"
            file.write_text("from-file")
            with file.open("r") as f:
                assert _read_input(None, f) == "from-file"
        elif scenario == "stdin":
            import io

            monkeypatch.setattr("sys.stdin", io.StringIO("from-stdin"))
            assert _read_input(None, None) == "from-stdin"
        elif scenario == "both_provided":
            file = tmp_path / "in.txt"
            file.write_text("x")
            with file.open("r") as f, pytest.raises(click.UsageError):
                _read_input("hello", f)


class TestCaseParseParams:
    @pytest.mark.parametrize(
        ["params", "expected", "raises"],
        [
            pytest.param(("temperature=0.7",), {"temperature": 0.7}, None, id="numeric"),
            pytest.param(("name=hello",), {"name": "hello"}, None, id="non_json_falls_back_to_string"),
            pytest.param(("a=1", "b=2"), {"a": 1, "b": 2}, None, id="multiple"),
            pytest.param(('payload={"a": 1}',), {"payload": {"a": 1}}, None, id="nested_json"),
            pytest.param(("bad-format",), None, click.BadParameter, id="missing_equals"),
        ],
    )
    def test__parse_params(
        self,
        params: tuple[str, ...],
        expected: dict[str, t.Any] | None,
        raises: type[BaseException] | None,
    ) -> None:
        if raises is not None:
            with pytest.raises(raises):
                _parse_params(params)
        else:
            assert _parse_params(params) == expected
