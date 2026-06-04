import dataclasses
import typing as t

import pytest

from flama import types
from flama.models.engine.llm.decoder import (
    ChannelPolicy,
    Decoder,
    MarkerScanner,
    PassthroughParser,
    PassthroughScanner,
)
from flama.models.engine.llm.decoder.decoder import (
    _KNOWN_CHANNEL_SCANNERS,
    _KNOWN_TOOL_PARSERS,
    _KNOWN_TOOL_SCANNERS,
    _ResolvedDecoder,
)
from flama.models.engine.llm.decoder.parsers import JSONObjectParser, JSONParser


class TestCaseLLMTypes:
    @pytest.mark.parametrize(
        ["literal", "registry"],
        [
            pytest.param(types.LLMEngineChannelScanners, _KNOWN_CHANNEL_SCANNERS, id="channel_scanners"),
            pytest.param(types.LLMEngineToolScanners, _KNOWN_TOOL_SCANNERS, id="tool_scanners"),
            pytest.param(types.LLMEngineToolParsers, _KNOWN_TOOL_PARSERS, id="tool_parsers"),
        ],
    )
    def test_registry_keys(self, literal: t.Any, registry: dict) -> None:
        assert set(t.get_args(literal)) == set(registry.keys())


class TestCaseChannelPolicy:
    def test_defaults(self) -> None:
        policy = ChannelPolicy()

        assert policy.output == ChannelPolicy.DEFAULT_OUTPUT == "output"
        assert policy.overrides is None

    @pytest.mark.parametrize(
        ["policy", "captured", "expected"],
        [
            pytest.param(ChannelPolicy(), "analysis", "analysis", id="captured"),
            pytest.param(ChannelPolicy(), None, None, id="unnamed_capture_returns_none"),
            pytest.param(ChannelPolicy(), "", None, id="empty_capture_returns_none"),
            pytest.param(ChannelPolicy(overrides={"analysis": "thinking"}), "analysis", "thinking", id="override_hit"),
            pytest.param(
                ChannelPolicy(overrides={"analysis": "thinking"}),
                None,
                None,
                id="override_does_not_apply_to_unnamed",
            ),
            pytest.param(
                ChannelPolicy(overrides={"analysis": "thinking"}),
                "other",
                "other",
                id="override_miss_round_trips",
            ),
        ],
    )
    def test_resolve(self, policy: ChannelPolicy, captured: str | None, expected: str | None) -> None:
        assert policy.resolve(captured) == expected


class TestCaseDecoder:
    @pytest.mark.parametrize(
        ["channel", "tool", "parser", "exception", "expected_channel", "expected_tool", "expected_parser"],
        [
            pytest.param(None, None, None, None, None, None, None, id="defaults_none"),
            pytest.param(
                "passthrough",
                "passthrough",
                "passthrough",
                None,
                PassthroughScanner,
                PassthroughScanner,
                PassthroughParser,
                id="passthrough_strings",
            ),
            pytest.param(
                "think",
                "tool_call",
                "json_object",
                None,
                _KNOWN_CHANNEL_SCANNERS["think"],
                _KNOWN_TOOL_SCANNERS["tool_call"],
                _KNOWN_TOOL_PARSERS["json_object"],
                id="registry_strings",
            ),
            pytest.param("not-a-key", "passthrough", "passthrough", KeyError, None, None, None, id="invalid_string"),
            pytest.param("off", None, None, KeyError, None, None, None, id="legacy_off_token"),
        ],
        indirect=["exception"],
    )
    def test_init(
        self,
        channel: t.Any,
        tool: t.Any,
        parser: t.Any,
        exception,
        expected_channel: t.Any,
        expected_tool: t.Any,
        expected_parser: t.Any,
    ) -> None:
        with exception:
            decoder = Decoder(channel, tool, parser)
            if expected_channel is None:
                assert decoder.channel_scanner is None
            elif isinstance(expected_channel, type):
                assert isinstance(decoder.channel_scanner, expected_channel)
            else:
                assert decoder.channel_scanner is expected_channel
            if expected_tool is None:
                assert decoder.tool_scanner is None
            elif isinstance(expected_tool, type):
                assert isinstance(decoder.tool_scanner, expected_tool)
            else:
                assert decoder.tool_scanner is expected_tool
            if expected_parser is None:
                assert decoder.tool_parser is None
            elif isinstance(expected_parser, type):
                assert isinstance(decoder.tool_parser, expected_parser)
            else:
                assert decoder.tool_parser is expected_parser
            assert decoder.policy == ChannelPolicy()

    def test_init_instance_inputs_pass_through(self) -> None:
        scanner = MarkerScanner(name="custom", start="<c>", end="</c>")
        parser = JSONObjectParser()

        decoder = Decoder(scanner, scanner, parser)

        assert decoder.channel_scanner is scanner
        assert decoder.tool_scanner is scanner
        assert decoder.tool_parser is parser

    def test_replace_yields_new_decoder(self) -> None:
        decoder = Decoder("think")

        replaced = dataclasses.replace(decoder, tool_scanner="tool_call", tool_parser="json_object")

        assert replaced is not decoder
        assert replaced.channel_scanner is _KNOWN_CHANNEL_SCANNERS["think"]
        assert replaced.tool_scanner is _KNOWN_TOOL_SCANNERS["tool_call"]

    @pytest.mark.parametrize(
        ["decoder", "expected"],
        [
            pytest.param(Decoder(), False, id="all_none"),
            pytest.param(Decoder("think"), False, id="partial"),
            pytest.param(Decoder("passthrough", "passthrough", "passthrough"), True, id="fully_resolved"),
        ],
    )
    def test_is_resolved(self, decoder: Decoder, expected: bool) -> None:
        assert decoder.is_resolved is expected

    @pytest.mark.parametrize(
        ["decoder", "samples", "expected"],
        [
            pytest.param(Decoder(), ("<think>r</think>",), _KNOWN_CHANNEL_SCANNERS["think"], id="think"),
            pytest.param(
                Decoder(),
                ("plain", "<|channel|>x<|message|>y<|end|>"),
                _KNOWN_CHANNEL_SCANNERS["harmony"],
                id="harmony_via_preflight",
            ),
            pytest.param(
                Decoder(),
                ("<|channel>analysis\nx<channel|>",),
                _KNOWN_CHANNEL_SCANNERS["channel"],
                id="channel",
            ),
            pytest.param(Decoder(), ("plain", "plain"), None, id="no_match"),
            pytest.param(Decoder(), (), None, id="no_samples"),
            pytest.param(Decoder(), ("", "<think>r</think>"), _KNOWN_CHANNEL_SCANNERS["think"], id="skip_empty"),
            pytest.param(
                Decoder(),
                ("<think>r</think>", "<|channel|>x<|message|>y<|end|>"),
                _KNOWN_CHANNEL_SCANNERS["think"],
                id="first_sample_wins",
            ),
            pytest.param(
                Decoder(channel_scanner=_KNOWN_CHANNEL_SCANNERS["harmony"]),
                ("<think>r</think>",),
                _KNOWN_CHANNEL_SCANNERS["harmony"],
                id="pinned_short_circuits",
            ),
        ],
    )
    def test_detect_channel_scanner(self, decoder: Decoder, samples: tuple[str, ...], expected: t.Any) -> None:
        assert decoder._detect_channel_scanner(*samples) is expected

    @pytest.mark.parametrize(
        ["decoder", "samples", "expected"],
        [
            pytest.param(
                Decoder(), ("emit <tool_call>{}</tool_call>",), _KNOWN_TOOL_SCANNERS["tool_call"], id="tool_call"
            ),
            pytest.param(Decoder(), ("[TOOL_CALLS][{}]",), _KNOWN_TOOL_SCANNERS["tool_calls"], id="tool_calls"),
            pytest.param(
                Decoder(),
                ("<|python_start|>x()<|python_end|>",),
                _KNOWN_TOOL_SCANNERS["python_block"],
                id="python_block",
            ),
            pytest.param(Decoder(), ("plain text",), None, id="no_match"),
            pytest.param(Decoder(), (), None, id="no_samples"),
            pytest.param(
                Decoder(), ("", "<tool_call>{}</tool_call>"), _KNOWN_TOOL_SCANNERS["tool_call"], id="skip_empty"
            ),
            pytest.param(
                Decoder(tool_scanner=_KNOWN_TOOL_SCANNERS["python_tag"]),
                ("<tool_call>{}</tool_call>",),
                _KNOWN_TOOL_SCANNERS["python_tag"],
                id="pinned_short_circuits",
            ),
        ],
    )
    def test_detect_tool_scanner(self, decoder: Decoder, samples: tuple[str, ...], expected: t.Any) -> None:
        assert decoder._detect_tool_scanner(*samples) is expected

    @pytest.mark.parametrize(
        ["decoder", "samples", "scanner", "expected_type", "expected_instance"],
        [
            pytest.param(
                Decoder(),
                ('<tool_call>{"name":"fn","arguments":{}}</tool_call>',),
                PassthroughScanner(),
                None,
                None,
                id="passthrough_scanner_yields_none",
            ),
            pytest.param(
                Decoder(),
                ('<tool_call>{"name":"fn","arguments":{}}</tool_call>',),
                _KNOWN_TOOL_SCANNERS["tool_call"],
                JSONParser,
                None,
                id="extracts_body_from_template",
            ),
            pytest.param(
                Decoder(),
                ("no marker here", '<tool_call>{"name":"fn","arguments":{}}</tool_call>'),
                _KNOWN_TOOL_SCANNERS["tool_call"],
                JSONParser,
                None,
                id="uses_preflight_when_template_misses",
            ),
            pytest.param(
                Decoder(),
                ('<|python_tag|>{"name":"fn","arguments":{}}',),
                _KNOWN_TOOL_SCANNERS["python_tag"],
                JSONParser,
                None,
                id="one_sided_marker",
            ),
            pytest.param(
                Decoder(),
                ("", "plain"),
                _KNOWN_TOOL_SCANNERS["tool_call"],
                None,
                None,
                id="no_sample_matches",
            ),
            pytest.param(
                Decoder(),
                ("<tool_call>unterminated",),
                _KNOWN_TOOL_SCANNERS["tool_call"],
                None,
                None,
                id="close_marker_missing",
            ),
            pytest.param(
                Decoder(),
                ("<tool_call>opaque non-json body</tool_call>",),
                _KNOWN_TOOL_SCANNERS["tool_call"],
                None,
                None,
                id="no_parser_recognises_body",
            ),
            pytest.param(
                Decoder(),
                # Qwen2.5 / Qwen2.5-Coder render the tools system prompt with a literal placeholder example
                # ahead of the synthetic assistant turn carrying the real JSON call; the detector must walk
                # past the unparseable placeholder body and pick up the second marker pair.
                (
                    "within <tool_call></tool_call> XML tags:\n"
                    "<tool_call>\n"
                    '{"name": <function-name>, "arguments": <args-json-object>}\n'
                    "</tool_call>\n"
                    "<|im_start|>assistant\n"
                    "<tool_call>\n"
                    '{"name": "fn", "arguments": {}}\n'
                    "</tool_call>",
                ),
                _KNOWN_TOOL_SCANNERS["tool_call"],
                JSONParser,
                None,
                id="walks_past_unparseable_first_body",
            ),
            pytest.param(
                Decoder(tool_parser=_KNOWN_TOOL_PARSERS["json_array"]),
                ("anything",),
                _KNOWN_TOOL_SCANNERS["tool_call"],
                None,
                _KNOWN_TOOL_PARSERS["json_array"],
                id="pinned_parser_short_circuits",
            ),
        ],
    )
    def test_detect_tool_parser(
        self,
        decoder: Decoder,
        samples: tuple[str, ...],
        scanner: t.Any,
        expected_type: type | None,
        expected_instance: t.Any,
    ) -> None:
        result = decoder._detect_tool_parser(*samples, scanner=scanner)

        if expected_instance is not None:
            assert result is expected_instance
        elif expected_type is None:
            assert result is None
        else:
            assert isinstance(result, expected_type)

    @pytest.mark.parametrize(
        ["scanner", "samples", "expected"],
        [
            pytest.param(
                _KNOWN_TOOL_SCANNERS["tool_call"],
                ("<tool_call>first</tool_call> middle <tool_call>second</tool_call>",),
                ["first", "second"],
                id="yields_every_two_sided_pair_in_order",
            ),
            pytest.param(
                _KNOWN_TOOL_SCANNERS["tool_call"],
                ("<tool_call>only-open",),
                [],
                id="stops_when_close_missing",
            ),
            pytest.param(
                _KNOWN_TOOL_SCANNERS["tool_call"],
                ("<tool_call>   </tool_call><tool_call>real</tool_call>",),
                ["real"],
                id="skips_whitespace_only_bodies",
            ),
            pytest.param(
                _KNOWN_TOOL_SCANNERS["python_tag"],
                ('<|python_tag|>{"name":"fn"} more text <|python_tag|>{"name":"other"}',),
                ['{"name":"fn"} more text <|python_tag|>{"name":"other"}'],
                id="one_sided_yields_first_body_only",
            ),
            pytest.param(
                _KNOWN_TOOL_SCANNERS["tool_call"],
                ("", "no markers", "<tool_call>body</tool_call>"),
                ["body"],
                id="walks_multiple_samples_in_order",
            ),
        ],
    )
    def test_iter_marker_bodies(
        self,
        scanner: t.Any,
        samples: tuple[str, ...],
        expected: list[str],
    ) -> None:
        assert list(Decoder._iter_marker_bodies(scanner, samples)) == expected

    @pytest.mark.parametrize(
        ["decoder", "samples", "expected_channel", "expected_tool", "expected_parser_type"],
        [
            pytest.param(
                Decoder(),
                ('<think>r</think><tool_call>{"name":"fn","arguments":{"x":1}}</tool_call>',),
                _KNOWN_CHANNEL_SCANNERS["think"],
                _KNOWN_TOOL_SCANNERS["tool_call"],
                JSONParser,
                id="all_three_detected",
            ),
            pytest.param(
                Decoder(),
                ("plain output",),
                PassthroughScanner,
                PassthroughScanner,
                PassthroughParser,
                id="no_match_falls_back_to_passthrough",
            ),
            pytest.param(
                Decoder(),
                (),
                PassthroughScanner,
                PassthroughScanner,
                PassthroughParser,
                id="no_samples_falls_back_to_passthrough",
            ),
            pytest.param(
                Decoder(),
                ("<think>r</think>", '<tool_call>{"name":"fn","arguments":{}}</tool_call>'),
                _KNOWN_CHANNEL_SCANNERS["think"],
                _KNOWN_TOOL_SCANNERS["tool_call"],
                JSONParser,
                id="template_then_preflight",
            ),
            pytest.param(
                Decoder(tool_scanner="tool_call"),
                ('<tool_call>{"name":"fn","arguments":{}}</tool_call>',),
                PassthroughScanner,
                _KNOWN_TOOL_SCANNERS["tool_call"],
                JSONParser,
                id="pinned_scanner_drives_parser",
            ),
        ],
    )
    def test_resolve(
        self,
        decoder: Decoder,
        samples: tuple[str, ...],
        expected_channel: t.Any,
        expected_tool: t.Any,
        expected_parser_type: type,
    ) -> None:
        resolved = decoder.resolve(*samples)

        if isinstance(expected_channel, type):
            assert isinstance(resolved.channel_scanner, expected_channel)
        else:
            assert resolved.channel_scanner is expected_channel
        if isinstance(expected_tool, type):
            assert isinstance(resolved.tool_scanner, expected_tool)
        else:
            assert resolved.tool_scanner is expected_tool
        assert isinstance(resolved.tool_parser, expected_parser_type)

    def test_custom_policy_propagates(self) -> None:
        policy = ChannelPolicy(output="answer", overrides={"analysis": "reasoning"})

        resolved = Decoder(policy=policy).resolve("<think>r</think>")

        assert resolved.policy is policy

    @pytest.mark.parametrize(
        ["samples", "expected_is_resolved"],
        [
            pytest.param(
                ('<think>r</think><tool_call>{"name":"fn","arguments":{}}</tool_call>',), True, id="all_detected"
            ),
            pytest.param(("plain",), False, id="no_match"),
            pytest.param(("<think>r</think>",), False, id="only_channel"),
            pytest.param(('<tool_call>{"name":"fn","arguments":{}}</tool_call>',), False, id="only_tool"),
            pytest.param(("<tool_call>opaque body</tool_call>",), False, id="marker_without_parseable_body"),
            pytest.param((), False, id="no_samples"),
        ],
    )
    def test_resolve_strict(self, samples: tuple[str, ...], expected_is_resolved: bool) -> None:
        resolved = Decoder().resolve(*samples, default=False)

        if expected_is_resolved:
            assert isinstance(resolved, _ResolvedDecoder)
        else:
            assert resolved is None
