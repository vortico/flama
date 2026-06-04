import json
import pathlib
import typing as t
from unittest.mock import MagicMock, call, patch

import click
import pytest
from click.testing import CliRunner

from flama._cli.commands.model import _LLM, _ML, _Cli, command
from flama.concurrency import iterate
from flama.models.base import LLMModel, MLModel
from flama.models.engine.llm.decoder.decoder import Decoder
from flama.models.transport.output.llm.event import Event, TextEvent


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


async def _llm_stream_two_tokens(prompt: str | None = None, /, **kwargs: t.Any) -> t.AsyncIterator[Event]:
    async def _gen() -> t.AsyncIterator[Event]:
        for text in ["Hello", " world"]:
            yield TextEvent(channel="output", text=text)

    return _gen()


async def _llm_stream_one_token(prompt: str | None = None, /, **kwargs: t.Any) -> t.AsyncIterator[Event]:
    async def _gen() -> t.AsyncIterator[Event]:
        yield TextEvent(channel="output", text="ok")

    return _gen()


async def _llm_stream_thinking_then_output(prompt: str | None = None, /, **kwargs: t.Any) -> t.AsyncIterator[Event]:
    async def _gen() -> t.AsyncIterator[Event]:
        yield TextEvent(channel="thinking", text="reasoning")
        yield TextEvent(channel="output", text="answer")

    return _gen()


class TestCaseCommand:
    @pytest.mark.parametrize(
        [
            "extra_args",
            "family",
            "expected_decoder",
            "expected_channel_name",
            "expected_tool_scanner_name",
            "expected_parser_classname",
        ],
        [
            pytest.param([], "ml", False, None, None, None, id="ml_family_skips_decoder"),
            pytest.param([], "llm", True, None, None, None, id="llm_family_default_auto"),
            pytest.param(
                ["--channel-scanner", "channel"],
                "llm",
                True,
                "channel",
                None,
                None,
                id="llm_with_channel_scanner",
            ),
            pytest.param(
                ["--channel-scanner", "passthrough"],
                "llm",
                True,
                "passthrough",
                None,
                None,
                id="llm_channel_scanner_passthrough",
            ),
            pytest.param(
                ["--tool-scanner", "tool_call"], "llm", True, None, "tool_call", None, id="llm_with_tool_scanner"
            ),
            pytest.param(
                ["--tool-scanner", "passthrough"],
                "llm",
                True,
                None,
                "passthrough",
                None,
                id="llm_tool_scanner_passthrough",
            ),
            pytest.param(
                ["--tool-parser", "json_object"],
                "llm",
                True,
                None,
                None,
                "JSONObjectParser",
                id="llm_with_tool_parser",
            ),
            pytest.param(
                ["--tool-parser", "passthrough"],
                "llm",
                True,
                None,
                None,
                "PassthroughParser",
                id="llm_tool_parser_passthrough",
            ),
            pytest.param(
                [
                    "--channel-scanner",
                    "harmony",
                    "--tool-scanner",
                    "tool_call",
                    "--tool-parser",
                    "json_object",
                ],
                "llm",
                True,
                "harmony",
                "tool_call",
                "JSONObjectParser",
                id="llm_all_three_set",
            ),
        ],
    )
    def test_command_normal_load(
        self,
        runner: CliRunner,
        ml_component: MagicMock,
        extra_args: list[str],
        family: str,
        expected_decoder: bool,
        expected_channel_name: str | None,
        expected_tool_scanner_name: str | None,
        expected_parser_classname: str | None,
    ) -> None:
        meta = MagicMock()
        meta.framework.family = family
        with (
            patch("flama._cli.commands.model.ModelComponentBuilder") as builder,
            patch("flama.serialize.serializer.Serializer.meta", return_value=meta),
        ):
            builder.build.return_value = ml_component
            result = runner.invoke(command, [*extra_args, "dummy.flm", "inspect"])

            assert result.exit_code == 0, result.output
            kwargs = builder.build.call_args.kwargs
            assert builder.build.call_args.args == ("dummy.flm",)
            assert "lib" not in kwargs
            assert kwargs["autoload"] is True
            decoder = kwargs["decoder"]

            if not expected_decoder:
                assert decoder is None
                return

            assert isinstance(decoder, Decoder)

            if expected_channel_name is None:
                assert decoder.channel_scanner is None
            else:
                assert decoder.channel_scanner is not None
                assert decoder.channel_scanner.name == expected_channel_name

            if expected_tool_scanner_name is None:
                assert decoder.tool_scanner is None
            else:
                assert decoder.tool_scanner is not None
                assert decoder.tool_scanner.name == expected_tool_scanner_name

            if expected_parser_classname is None:
                assert decoder.tool_parser is None
            else:
                assert decoder.tool_parser is not None
                assert type(decoder.tool_parser).__name__ == expected_parser_classname

    @pytest.mark.parametrize(
        ["extra_args", "error_fragment"],
        [
            pytest.param(
                ["--channel-scanner", "bogus"],
                "Invalid value for '--channel-scanner'",
                id="channel_scanner_rejects_unknown",
            ),
            pytest.param(
                ["--tool-scanner", "bogus"],
                "Invalid value for '--tool-scanner'",
                id="tool_scanner_rejects_unknown",
            ),
            pytest.param(
                ["--tool-parser", "bogus"],
                "Invalid value for '--tool-parser'",
                id="tool_parser_rejects_unknown",
            ),
        ],
    )
    def test_command_rejects_invalid_options(
        self,
        runner: CliRunner,
        ml_component: MagicMock,
        extra_args: list[str],
        error_fragment: str,
    ) -> None:
        with patch("flama._cli.commands.model.ModelComponentBuilder") as builder:
            builder.build.return_value = ml_component
            result = runner.invoke(command, [*extra_args, "dummy.flm", "inspect"])

            assert result.exit_code != 0
            assert error_fragment in result.output

    def test_command_file_not_found(self, runner: CliRunner, ml_component: MagicMock) -> None:
        with patch("flama.serialize.serializer.Serializer.meta", side_effect=FileNotFoundError("no")):
            result = runner.invoke(command, ["missing.flm", "inspect"])

            assert result.exit_code != 0
            assert "Model file not found" in result.output

    def test_inspect_does_not_trigger_load(self, runner: CliRunner, ml_component: MagicMock) -> None:
        meta = MagicMock()
        meta.framework.family = "ml"
        with (
            patch("flama._cli.commands.model.ModelComponentBuilder") as builder,
            patch("flama.serialize.serializer.Serializer.meta", return_value=meta),
        ):
            builder.build.return_value = ml_component
            result = runner.invoke(command, ["dummy.flm", "inspect"])

            assert result.exit_code == 0, result.output
            assert not ml_component.load.called


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
        assert component.model.inspect.call_count == 1


class TestCaseRun:
    @pytest.fixture(scope="function")
    def input_file(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "in.json"
        path.write_text(json.dumps([[0, 0]]))
        return path

    @pytest.mark.parametrize(
        ["ml_component", "scenario"],
        [
            pytest.param(MLModel, "via_file", id="via_file"),
            pytest.param(MLModel, "via_stdin", id="via_stdin"),
            pytest.param(MLModel, "invalid_json", id="invalid_json"),
            pytest.param(MLModel, "with_param_rejected", id="with_param_rejected"),
            pytest.param(MLModel, "with_channel_rejected", id="with_channel_rejected"),
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
            result = runner.invoke(command, ["dummy.flm", "run", "-i", str(input_file)])

            assert result.exit_code == 0, result.output
            assert ml_component.model.predict.call_args_list == [call([[0, 0]])]
        elif scenario == "via_stdin":
            result = runner.invoke(command, ["dummy.flm", "run"], input="[[3, 4]]")

            assert result.exit_code == 0, result.output
            assert ml_component.model.predict.call_args_list == [call([[3, 4]])]
        elif scenario == "invalid_json":
            result = runner.invoke(command, ["dummy.flm", "run"], input="not json")

            assert result.exit_code != 0
            assert "valid JSON" in result.output
        elif scenario == "with_param_rejected":
            result = runner.invoke(
                command,
                ["dummy.flm", "run", "--param", "temperature=0.7"],
                input="[[0]]",
            )

            assert result.exit_code != 0
            assert "--param" in result.output
        elif scenario == "with_channel_rejected":
            result = runner.invoke(
                command,
                ["dummy.flm", "run", "--channel", "all"],
                input="[[0]]",
            )

            assert result.exit_code != 0
            assert "--channel" in result.output

    @pytest.mark.parametrize(
        ["llm_component", "scenario"],
        [
            pytest.param(LLMModel, "via_file", id="via_file"),
            pytest.param(LLMModel, "via_stdin", id="via_stdin"),
            pytest.param(LLMModel, "with_params", id="with_params"),
            pytest.param(LLMModel, "output_to_file", id="output_to_file"),
            pytest.param(LLMModel, "pretty", id="pretty"),
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
        if scenario == "via_file":
            prompt = tmp_path / "prompt.txt"
            prompt.write_text("What is Python?")
            result = runner.invoke(command, ["dummy.flm", "run", "-i", str(prompt)])

            assert result.exit_code == 0, result.output
            assert "Hello world" in result.output
        elif scenario == "via_stdin":
            result = runner.invoke(command, ["dummy.flm", "run"], input="What is Python?")

            assert result.exit_code == 0, result.output
            assert "Hello world" in result.output
        elif scenario == "with_params":
            captured: dict[str, t.Any] = {}

            async def _capturing_query(prompt: str | None = None, /, **kwargs: t.Any) -> list[Event]:
                captured["prompt"] = prompt
                captured.update(kwargs)
                return [TextEvent(channel="output", text="Hello world")]

            llm_component.model.query = _capturing_query
            result = runner.invoke(
                command,
                ["dummy.flm", "run", "--param", "temperature=0.7", "--param", "max_tokens=100"],
                input="hello",
            )

            assert result.exit_code == 0, result.output
            assert captured["temperature"] == 0.7
            assert captured["max_tokens"] == 100
        elif scenario == "output_to_file":
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "run", "-o", str(output)],
                input="hello",
            )

            assert result.exit_code == 0, result.output
            assert "Hello world" in output.read_text()
        elif scenario == "pretty":
            result = runner.invoke(command, ["dummy.flm", "run", "--pretty"], input="hello")

            assert result.exit_code == 0, result.output

    @pytest.mark.parametrize(
        ["llm_component", "args", "expected_text", "expected_json"],
        [
            pytest.param(LLMModel, [], "answer", None, id="default_only_output"),
            pytest.param(
                LLMModel,
                ["--channel", "all"],
                None,
                [
                    {"channel": "thinking", "text": "reasoning"},
                    {"channel": "output", "text": "answer"},
                ],
                id="channel_all_wildcard",
            ),
            pytest.param(
                LLMModel,
                ["--channel", "*"],
                None,
                [
                    {"channel": "thinking", "text": "reasoning"},
                    {"channel": "output", "text": "answer"},
                ],
                id="channel_star_wildcard",
            ),
            pytest.param(LLMModel, ["--channel", "thinking"], "reasoning", None, id="channel_single_thinking"),
            pytest.param(
                LLMModel,
                ["--channel", "thinking", "--channel", "output"],
                None,
                [
                    {"channel": "thinking", "text": "reasoning"},
                    {"channel": "output", "text": "answer"},
                ],
                id="channel_multi_explicit",
            ),
            pytest.param(LLMModel, ["--channel", "missing"], "", None, id="channel_unknown_filters_all"),
        ],
        indirect=["llm_component"],
    )
    def test_run_llm_channels(
        self,
        runner: CliRunner,
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        args: list[str],
        expected_text: str | None,
        expected_json: list[dict[str, str]] | None,
    ) -> None:
        async def _mixed_query(prompt: str | None = None, /, **kwargs: t.Any) -> list[Event]:
            return [
                TextEvent(channel="thinking", text="reasoning"),
                TextEvent(channel="output", text="answer"),
            ]

        llm_component.model.query = _mixed_query

        result = runner.invoke(command, ["dummy.flm", "run", *args], input="hello")

        assert result.exit_code == 0, result.output
        if expected_json is not None:
            assert json.loads(result.output) == expected_json
        else:
            assert expected_text is not None
            assert result.output.strip() == expected_text

    @pytest.mark.parametrize(
        ["llm_component", "scenario"],
        [
            pytest.param(LLMModel, "with_system", id="with_system"),
            pytest.param(LLMModel, "transport_raw", id="transport_raw"),
            pytest.param(LLMModel, "transport_chat", id="transport_chat"),
            pytest.param(LLMModel, "transport_conversation", id="transport_conversation"),
            pytest.param(LLMModel, "system_with_raw_rejected", id="system_with_raw_rejected"),
            pytest.param(LLMModel, "default_transport_raw", id="default_transport_raw"),
        ],
        indirect=["llm_component"],
    )
    def test_run_llm_transport(
        self,
        runner: CliRunner,
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        tmp_path: pathlib.Path,
        scenario: str,
    ) -> None:
        captured: list[tuple[str | None, dict[str, t.Any]]] = []

        async def _capturing_query(prompt: str | None = None, /, **kwargs: t.Any) -> list[Event]:
            captured.append((prompt, kwargs))
            return [TextEvent(channel="output", text="Hello world")]

        llm_component.model.query = _capturing_query

        args, stdin, expected = self._transport_scenario(scenario, tmp_path, llm_component)
        result = runner.invoke(command, args, input=stdin)

        if expected.get("error"):
            assert result.exit_code != 0
            assert expected["error"] in result.output.lower()
            return

        assert result.exit_code == 0, result.output
        actual_prompt, actual_kwargs = captured[0]
        if "prompt" in expected:
            assert actual_prompt == expected["prompt"]
        for key, value in expected.get("kwargs", {}).items():
            assert actual_kwargs.get(key) == value

    @staticmethod
    def _transport_scenario(
        scenario: str, tmp_path: pathlib.Path, llm_component: MagicMock
    ) -> tuple[list[str], str | None, dict[str, t.Any]]:
        if scenario == "with_system":
            return (
                ["dummy.flm", "run", "--system", "be brief"],
                "hello",
                {"prompt": "hello", "kwargs": {"transport": "chat", "system": "be brief"}},
            )
        if scenario == "transport_raw":
            return (
                ["dummy.flm", "run", "--transport", "raw"],
                "hello",
                {"prompt": "hello", "kwargs": {"transport": "raw"}},
            )
        if scenario == "transport_chat":
            return (
                ["dummy.flm", "run", "--transport", "chat"],
                "hello",
                {"prompt": "hello", "kwargs": {"transport": "chat"}},
            )
        if scenario == "transport_conversation":
            conv = tmp_path / "conv.json"
            conv.write_text('[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]')
            return (
                ["dummy.flm", "run", "--transport", "conversation", "-i", str(conv)],
                None,
                {"prompt": None, "kwargs": {"transport": "conversation"}},
            )
        if scenario == "system_with_raw_rejected":
            return (
                ["dummy.flm", "run", "--transport", "raw", "--system", "boom"],
                "hi",
                {"error": "system"},
            )
        llm_component.model.default_transport = "raw"
        return (
            ["dummy.flm", "run"],
            "hello",
            {"prompt": "hello", "kwargs": {"transport": "raw"}},
        )


class TestCaseStream:
    @pytest.fixture(scope="function")
    def input_file(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "in.json"
        path.write_text(json.dumps([[0, 0]]))
        return path

    @pytest.mark.parametrize(
        ["ml_component", "scenario", "expected_output"],
        [
            pytest.param(MLModel, "streaming", "[1][2]", id="streaming"),
            pytest.param(MLModel, "buffered", "[1][2]\n", id="buffered"),
            pytest.param(MLModel, "invalid_json", None, id="invalid_json"),
            pytest.param(MLModel, "output_to_file", None, id="output_to_file"),
            pytest.param(MLModel, "with_param_rejected", None, id="with_param_rejected"),
            pytest.param(MLModel, "with_channel_rejected", None, id="with_channel_rejected"),
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
            result = runner.invoke(command, ["dummy.flm", "stream", "-i", str(input_file)])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "buffered":
            result = runner.invoke(command, ["dummy.flm", "stream", "-i", str(input_file), "--buffer"])

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "invalid_json":
            result = runner.invoke(command, ["dummy.flm", "stream"], input="not json")

            assert result.exit_code != 0
            assert "valid JSON" in result.output
        elif scenario == "output_to_file":
            ml_component.model.stream = _ml_stream_one_item
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-i", str(input_file), "-o", str(output)],
            )

            assert result.exit_code == 0, result.output
            assert "[42]" in output.read_text()
        elif scenario == "with_param_rejected":
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "--param", "temperature=0.7"],
                input="[[0]]",
            )

            assert result.exit_code != 0
            assert "--param" in result.output
        elif scenario == "with_channel_rejected":
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "--channel", "all"],
                input="[[0]]",
            )

            assert result.exit_code != 0
            assert "--channel" in result.output

    @pytest.mark.parametrize(
        ["llm_component", "scenario", "expected_output"],
        [
            pytest.param(LLMModel, "streaming", "Hello world", id="streaming"),
            pytest.param(LLMModel, "buffered", "Hello world\n", id="buffered"),
            pytest.param(LLMModel, "with_params", None, id="with_params"),
            pytest.param(LLMModel, "with_system", None, id="with_system"),
            pytest.param(LLMModel, "transport_conversation", None, id="transport_conversation"),
            pytest.param(LLMModel, "output_to_file", None, id="output_to_file"),
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
            result = runner.invoke(command, ["dummy.flm", "stream"], input="test")

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "buffered":
            result = runner.invoke(command, ["dummy.flm", "stream", "--buffer"], input="test")

            assert result.exit_code == 0, result.output
            assert result.output == expected_output
        elif scenario == "with_params":
            captured: dict[str, t.Any] = {}

            async def _capturing_stream(prompt: str | None = None, /, **kwargs: t.Any) -> t.AsyncIterator[Event]:
                captured["prompt"] = prompt
                captured.update(kwargs)
                return await _llm_stream_one_token()

            llm_component.model.stream = _capturing_stream
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "--param", "temperature=0.7", "--param", "max_tokens=100"],
                input="hello",
            )

            assert result.exit_code == 0, result.output
            assert captured["temperature"] == 0.7
            assert captured["max_tokens"] == 100
        elif scenario == "with_system":
            captured_args: list[tuple[str | None, dict[str, t.Any]]] = []

            async def _capturing_stream(prompt: str | None = None, /, **kwargs: t.Any) -> t.AsyncIterator[Event]:
                captured_args.append((prompt, kwargs))
                return await _llm_stream_one_token()

            llm_component.model.stream = _capturing_stream
            result = runner.invoke(command, ["dummy.flm", "stream", "--system", "be brief"], input="hello")

            assert result.exit_code == 0, result.output
            assert captured_args[0][0] == "hello"
            assert captured_args[0][1].get("transport") == "chat"
            assert captured_args[0][1].get("system") == "be brief"
        elif scenario == "transport_conversation":
            captured_args = []

            async def _capturing_stream(prompt: str | None = None, /, **kwargs: t.Any) -> t.AsyncIterator[Event]:
                captured_args.append((prompt, kwargs))
                return await _llm_stream_one_token()

            llm_component.model.stream = _capturing_stream
            conv = tmp_path / "conv.json"
            conv.write_text('[{"role": "user", "content": "hi"}]')
            result = runner.invoke(command, ["dummy.flm", "stream", "--transport", "conversation", "-i", str(conv)])

            assert result.exit_code == 0, result.output
            assert captured_args[0][0] is None
            assert captured_args[0][1].get("transport") == "conversation"
            messages = captured_args[0][1].get("messages")
            assert messages is not None
            assert messages[0].role == "user"
        elif scenario == "output_to_file":
            llm_component.model.stream = _llm_stream_one_token
            output = tmp_path / "out.txt"
            result = runner.invoke(
                command,
                ["dummy.flm", "stream", "-o", str(output)],
                input="hello",
            )

            assert result.exit_code == 0, result.output
            assert "ok" in output.read_text()

    @pytest.mark.parametrize(
        ["llm_component", "args", "expected_substrings", "forbidden_substrings"],
        [
            pytest.param(LLMModel, [], ["answer"], ["reasoning", "[thinking]", "[output]"], id="default_only_output"),
            pytest.param(
                LLMModel,
                ["--channel", "all"],
                ["[thinking] reasoning", "[output] answer"],
                [],
                id="channel_all_wildcard",
            ),
            pytest.param(
                LLMModel,
                ["--channel", "*"],
                ["[thinking] reasoning", "[output] answer"],
                [],
                id="channel_star_wildcard",
            ),
            pytest.param(
                LLMModel,
                ["--channel", "thinking"],
                ["reasoning"],
                ["answer", "[thinking]", "[output]"],
                id="channel_single_thinking",
            ),
            pytest.param(
                LLMModel,
                ["--channel", "thinking", "--channel", "output"],
                ["[thinking] reasoning", "[output] answer"],
                [],
                id="channel_multi_explicit",
            ),
        ],
        indirect=["llm_component"],
    )
    def test_stream_llm_channels(
        self,
        runner: CliRunner,
        llm_component: MagicMock,
        patched_llm_builder: MagicMock,
        args: list[str],
        expected_substrings: list[str],
        forbidden_substrings: list[str],
    ) -> None:
        llm_component.model.stream = _llm_stream_thinking_then_output

        result = runner.invoke(command, ["dummy.flm", "stream", *args], input="test")

        assert result.exit_code == 0, result.output
        for token in expected_substrings:
            assert token in result.output
        for token in forbidden_substrings:
            assert token not in result.output


class TestCaseLLM:
    @pytest.fixture
    def llm_runner(self) -> _LLM:
        model = MagicMock(spec=LLMModel)
        model.default_transport = "chat"
        return _LLM(model)

    @pytest.mark.parametrize(
        ["param", "channels", "expected_model_kwargs", "expected_channels", "exception"],
        [
            pytest.param(
                ("temperature=0.7",), (), {"temperature": 0.7}, frozenset({"output"}), None, id="param_numeric"
            ),
            pytest.param(
                ("name=hello",), (), {"name": "hello"}, frozenset({"output"}), None, id="param_non_json_string"
            ),
            pytest.param(("a=1", "b=2"), (), {"a": 1, "b": 2}, frozenset({"output"}), None, id="param_multiple"),
            pytest.param(
                ('payload={"a": 1}',), (), {"payload": {"a": 1}}, frozenset({"output"}), None, id="param_nested_json"
            ),
            pytest.param(("bad-format",), (), None, None, click.BadParameter, id="param_missing_equals"),
            pytest.param((), (), {}, frozenset({"output"}), None, id="channels_empty_defaults_to_output"),
            pytest.param((), ("output",), {}, frozenset({"output"}), None, id="channels_single_explicit"),
            pytest.param(
                (), ("thinking", "output"), {}, frozenset({"thinking", "output"}), None, id="channels_multi_explicit"
            ),
            pytest.param((), ("all",), {}, None, None, id="channels_wildcard_all"),
            pytest.param((), ("*",), {}, None, None, id="channels_wildcard_star"),
            pytest.param((), ("thinking", "all"), {}, None, None, id="channels_wildcard_overrides"),
            pytest.param((), ("a", "a", "b"), {}, frozenset({"a", "b"}), None, id="channels_duplicates_deduped"),
        ],
        indirect=["exception"],
    )
    def test_parse_args(
        self,
        llm_runner: _LLM,
        param: tuple[str, ...],
        channels: tuple[str, ...],
        expected_model_kwargs: dict[str, t.Any] | None,
        expected_channels: frozenset[str] | None,
        exception,
    ) -> None:
        with exception:
            args = llm_runner._parse_args(transport=None, system=None, param=param, channels=channels)
            if expected_model_kwargs is not None:
                for key, value in expected_model_kwargs.items():
                    assert args["model_kwargs"][key] == value
            assert args["channels"] == expected_channels


class TestCaseCli:
    @pytest.mark.parametrize(
        ["spec", "expected_cls", "exception"],
        [
            pytest.param(LLMModel, _LLM, None, id="llm"),
            pytest.param(MLModel, _ML, None, id="ml"),
            pytest.param(object, None, click.UsageError, id="unsupported"),
        ],
        indirect=["exception"],
    )
    def test_build(self, spec: type, expected_cls: type[_Cli] | None, exception) -> None:
        component = MagicMock()
        component.model = MagicMock(spec=spec)

        with exception:
            runner = _Cli.build(component)
            assert isinstance(runner, expected_cls)  # ty: ignore[invalid-argument-type]
            assert runner.model is component.model
