import pathlib
import typing as t
from unittest.mock import MagicMock, call, patch

import click
import pytest
from click.testing import CliRunner

from flama._cli.commands.llm import _parse_params, command
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
        llm_component: MagicMock,
        scenario: str,
    ) -> None:
        with patch("flama._cli.commands.llm.LLMModelComponentBuilder") as builder:
            if scenario == "normal_load":
                builder.load.return_value = llm_component
                result = runner.invoke(command, ["dummy.flm", "inspect"])

                assert result.exit_code == 0, result.output
                builder.load.assert_called_once_with("dummy.flm")
            elif scenario == "file_not_found":
                builder.load.side_effect = FileNotFoundError("no")
                result = runner.invoke(command, ["missing.flm", "inspect"])

                assert result.exit_code != 0
                assert "Model file not found" in result.output


class TestCaseRun:
    def test_run(self, runner: CliRunner) -> None:
        with (
            patch("flama.Flama") as flama_cls,
            patch("flama._cli.config.app.FlamaApp") as flama_app_cls,
            patch("flama._cli.commands.llm.Config") as config_cls,
            patch("flama._cli.commands.llm.LLMModelComponentBuilder") as builder,
        ):
            app_instance = MagicMock()
            flama_cls.return_value = app_instance
            result = runner.invoke(command, ["dummy.flm", "run"])

        assert result.exit_code == 0, result.output
        builder.load.assert_not_called()
        flama_cls.assert_called_once()
        app_instance.models.add_llm.assert_called_once_with(path="/", model="dummy.flm", name="llm")
        flama_app_cls.assert_called_once_with(app=app_instance)
        config_cls.assert_called_once()
        config_cls.return_value.run.assert_called_once()


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
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        scenario: str,
    ) -> None:
        args = ["dummy.flm", "inspect"]
        if scenario == "pretty":
            args.append("--pretty")

        result = runner.invoke(command, args)

        assert result.exit_code == 0, result.output
        llm_component.model.inspect.assert_called_once()


class TestCaseConfigure:
    @pytest.mark.parametrize(
        ["llm_component", "scenario"],
        [
            pytest.param(BaseLLMModel, "default", id="default"),
            pytest.param(BaseLLMModel, "pretty", id="pretty"),
            pytest.param(BaseMLModel, "wrong_type", id="wrong_type"),
            pytest.param(BaseLLMModel, "invalid_param", id="invalid_param"),
        ],
        indirect=["llm_component"],
    )
    def test_configure(
        self,
        runner: CliRunner,
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        scenario: str,
    ) -> None:
        if scenario == "default":
            result = runner.invoke(
                command,
                ["dummy.flm", "configure", "--param", "temperature=0.7", "--param", "max_tokens=100"],
            )

            assert result.exit_code == 0, result.output
            assert llm_component.model.configure.call_args_list == [call({"temperature": 0.7, "max_tokens": 100})]
        elif scenario == "pretty":
            llm_component.model.params = {"temperature": 0.7}
            result = runner.invoke(
                command,
                ["dummy.flm", "configure", "--param", "temperature=0.7", "--pretty"],
            )

            assert result.exit_code == 0, result.output
        elif scenario == "wrong_type":
            result = runner.invoke(
                command,
                ["dummy.flm", "configure", "--param", "temperature=0.7"],
            )

            assert result.exit_code != 0
            assert "LLM" in result.output
        elif scenario == "invalid_param":
            result = runner.invoke(
                command,
                ["dummy.flm", "configure", "--param", "bad-format"],
            )

            assert result.exit_code != 0


class TestCaseQuery:
    @pytest.mark.parametrize(
        ["llm_component", "scenario"],
        [
            pytest.param(BaseLLMModel, "default", id="default"),
            pytest.param(BaseLLMModel, "with_params", id="with_params"),
            pytest.param(BaseLLMModel, "output_to_file", id="output_to_file"),
            pytest.param(BaseMLModel, "wrong_type", id="wrong_type"),
        ],
        indirect=["llm_component"],
    )
    def test_query(
        self,
        runner: CliRunner,
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        tmp_path: pathlib.Path,
        scenario: str,
    ) -> None:
        if scenario == "default":
            result = runner.invoke(command, ["dummy.flm", "query", "-p", "What is Python?"])

            assert result.exit_code == 0, result.output
            assert "Hello world" in result.output
        elif scenario == "with_params":
            captured: list[tuple[tuple[t.Any, ...], dict[str, t.Any]]] = []

            async def _capturing_query(prompt: str, **params: t.Any) -> str:
                captured.append(((prompt,), params))
                return "Hello world"

            llm_component.model.query = _capturing_query
            result = runner.invoke(
                command,
                ["dummy.flm", "query", "-p", "hello", "--param", "temperature=0.7"],
            )

            assert result.exit_code == 0, result.output
            assert captured == [(("hello",), {"temperature": 0.7})]
        elif scenario == "output_to_file":
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "query", "-p", "hello", "-o", str(output)],
            )

            assert result.exit_code == 0, result.output
            assert "Hello world" in output.read_text()
        elif scenario == "wrong_type":
            result = runner.invoke(command, ["dummy.flm", "query", "-p", "hello"])

            assert result.exit_code != 0
            assert "LLM" in result.output


class TestCaseStream:
    @pytest.mark.parametrize(
        ["llm_component", "scenario", "expected_output"],
        [
            pytest.param(BaseLLMModel, "streaming", '"Hello"" world"', id="streaming"),
            pytest.param(BaseLLMModel, "buffered", '"Hello"" world"\n', id="buffered"),
            pytest.param(BaseLLMModel, "with_params", None, id="with_params"),
            pytest.param(BaseLLMModel, "output_to_file", None, id="output_to_file"),
            pytest.param(BaseMLModel, "wrong_type", None, id="wrong_type"),
        ],
        indirect=["llm_component"],
    )
    def test_stream(
        self,
        runner: CliRunner,
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        tmp_path: pathlib.Path,
        scenario: str,
        expected_output: str | None,
    ) -> None:
        async def _stream(prompt: str, **params: t.Any) -> t.AsyncIterator[str]:
            for token in ["Hello", " world"]:
                yield token

        llm_component.model.stream = _stream

        if scenario == "streaming":
            result = runner.invoke(command, ["dummy.flm", "stream", "-p", "test"])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "buffered":
            result = runner.invoke(command, ["dummy.flm", "stream", "-p", "test", "--buffer"])

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
                ["dummy.flm", "stream", "-p", "hello", "--param", "temperature=0.7", "--param", "max_tokens=100"],
            )

            assert result.exit_code == 0, result.output
            assert captured == {"temperature": 0.7, "max_tokens": 100}
        elif scenario == "output_to_file":

            async def _short_stream(prompt: str, **params: t.Any) -> t.AsyncIterator[str]:
                yield "ok"

            llm_component.model.stream = _short_stream
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-p", "hello", "-o", str(output)],
            )

            assert result.exit_code == 0, result.output
            assert '"ok"' in output.read_text()
        elif scenario == "wrong_type":
            result = runner.invoke(command, ["dummy.flm", "stream", "-p", "hello"])

            assert result.exit_code != 0
            assert "LLM" in result.output


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
