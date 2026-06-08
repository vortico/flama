import asyncio
import logging
import uuid
from unittest.mock import patch

import pytest

from flama import exceptions
from flama.models.engine.llm.codec import _FSM, PREFLIGHT_MAX_CHARS, PREFLIGHT_MAX_TOKENS, LLMCodec
from flama.models.engine.llm.decoder.decoder import _KNOWN_CHANNEL_SCANNERS, _KNOWN_TOOL_SCANNERS, Decoder
from flama.models.engine.llm.decoder.markers import PassthroughScanner, Scanner
from flama.models.engine.llm.decoder.parsers import (
    JSONArrayParser,
    JSONObjectParser,
    JSONParser,
    JSONSequenceParser,
    PassthroughParser,
    PythonicParser,
    ToolParser,
)
from flama.models.engine.llm.delta import EngineDelta
from flama.models.transport.output.llm.event import TextEvent, ToolEvent, TraceEvent
from tests.unit.models.engine.llm.conftest import FakeLLMBackend, FakeModel, aiter, consume, make_engine

_THINK_SCANNER = _KNOWN_CHANNEL_SCANNERS["think"]
_CHANNEL_SCANNER = _KNOWN_CHANNEL_SCANNERS["channel"]
_HARMONY_SCANNER = _KNOWN_CHANNEL_SCANNERS["harmony"]
_TOOL_CALL_SCANNER = _KNOWN_TOOL_SCANNERS["tool_call"]
_PYTHON_TAG_SCANNER = _KNOWN_TOOL_SCANNERS["python_tag"]
_PYTHONIC_SCANNER = _KNOWN_TOOL_SCANNERS["pythonic"]


class TestCaseFSM:
    def test_initial_state(self) -> None:
        fsm = _FSM(Decoder("passthrough", "passthrough", "passthrough").resolve())

        assert fsm._state == "outside"
        assert fsm._channel == "output"
        assert fsm._tool_count == 0
        assert fsm._engine_reason is None

    def test_transitions_table(self) -> None:
        for (state, kind, source), action in _FSM._TRANSITIONS.items():
            assert state in ("outside", "channel", "tool")
            assert kind in ("content", "open", "close")
            assert source in ("channel", "tool")
            assert callable(action)

    @pytest.mark.parametrize(
        ["engine_reason", "tool_count", "expected", "warns"],
        [
            pytest.param(None, 0, "stop", False, id="silent_engine_no_tools"),
            pytest.param(None, 2, "tool_use", False, id="silent_engine_with_tools"),
            pytest.param("stop", 0, "stop", False, id="stop_no_tools"),
            pytest.param("stop", 1, "tool_use", False, id="stop_promotes_with_tool"),
            pytest.param("length", 0, "max_tokens", False, id="length"),
            pytest.param("length", 1, "max_tokens", False, id="length_not_promoted_under_truncation"),
            pytest.param("tool_calls", 0, "tool_use", False, id="tool_calls_no_tools_emitted"),
            pytest.param("tool_calls", 1, "tool_use", False, id="tool_calls_with_tools"),
            pytest.param("quasi_stop", 0, "unknown", True, id="unmapped_warns"),
            pytest.param("quasi_stop", 1, "unknown", True, id="unmapped_not_promoted"),
        ],
    )
    def test_terminate(
        self,
        engine_reason: str | None,
        tool_count: int,
        expected: str,
        warns: bool,
        caplog_flama: pytest.LogCaptureFixture,
    ) -> None:
        fsm = _FSM(Decoder("passthrough", "passthrough", "passthrough").resolve())
        fsm._engine_reason = engine_reason
        fsm._tool_count = tool_count

        with caplog_flama.at_level(logging.WARNING, logger="flama.models.engine.llm.codec"):
            stop = fsm.terminate(7)

        assert stop.stop_reason == expected
        assert stop.output_tokens == 7
        assert ("Unmapped backend finish_reason" in caplog_flama.text) is warns

    async def test_feed_increments_tool_count(self) -> None:
        engine = make_engine(tool_scanner=_TOOL_CALL_SCANNER, tool_parser=JSONObjectParser())
        fsm = _FSM(engine.decoder)

        list(fsm.feed(EngineDelta(text='<tool_call>{"name":"a","arguments":{}}</tool_call>')))
        list(fsm.feed(EngineDelta(text='<tool_call>{"name":"b","arguments":{}}</tool_call>')))

        assert fsm._tool_count == 2

    async def test_feed_latches_finish_reason(self) -> None:
        fsm = _FSM(Decoder("passthrough", "passthrough", "passthrough").resolve())

        list(fsm.feed(EngineDelta(text="hi", token_count=2)))
        assert fsm._engine_reason is None

        list(fsm.feed(EngineDelta(token_count=2, finish_reason="length")))
        assert fsm._engine_reason == "length"


class TestCaseLLMCodec:
    """Cover :class:`LLMCodec` end-to-end: the lazily-resolved ``decoder`` property, the three-stage
    detection cascade, the chat-template / preflight probe helpers, and the streaming ``decode``
    state machine that turns engine deltas into transport-level events.
    """

    def test_decoder_raises_when_not_detected(self) -> None:
        engine = LLMCodec(None)

        with pytest.raises(exceptions.ApplicationError, match="Decoder is not detected"):
            engine.decoder

    def test_decoder_setter_and_deleter(self) -> None:
        engine = LLMCodec(None)
        resolved = Decoder("passthrough", "passthrough", "passthrough").resolve()

        engine.decoder = resolved
        assert engine.decoder is resolved

        del engine.decoder
        with pytest.raises(exceptions.ApplicationError):
            engine.decoder

    async def test_detect_three_stage_cascade(self) -> None:
        backend = FakeLLMBackend(
            chunks=["<think>r</think>"],
            chat_template_sample='<tool_call>{"name":"x","arguments":{}}</tool_call>',
        )
        engine = LLMCodec(None)

        await engine.detect(FakeModel(backend))

        assert engine.decoder.channel_scanner is _KNOWN_CHANNEL_SCANNERS["think"]
        assert engine.decoder.tool_scanner is _KNOWN_TOOL_SCANNERS["tool_call"]

    async def test_detect_idempotent(self) -> None:
        backend = FakeLLMBackend(chunks=["<think>r</think>"], chat_template_sample="<tool_call>{}</tool_call>")
        engine = LLMCodec(None)

        await engine.detect(FakeModel(backend))
        first = engine.decoder
        await engine.detect(FakeModel(backend))

        assert engine.decoder is first
        assert len(backend.generate_calls) == 1
        assert backend.chat_template_sample_calls == 1

    async def test_detect_concurrent_calls_run_once(self) -> None:
        backend = FakeLLMBackend(chunks=["<think>r</think>"], chat_template_sample="<tool_call>{}</tool_call>")
        engine = LLMCodec(None)
        model = FakeModel(backend)

        await asyncio.gather(engine.detect(model), engine.detect(model), engine.detect(model))

        assert engine.decoder.channel_scanner is _KNOWN_CHANNEL_SCANNERS["think"]
        assert len(backend.generate_calls) == 1
        assert backend.chat_template_sample_calls == 1

    async def test_detect_fully_pinned_skips_all_io(self) -> None:
        backend = FakeLLMBackend(
            chunks=["<|channel|>x<|message|>y<|end|>"], chat_template_sample="<tool_call>{}</tool_call>"
        )
        engine = LLMCodec(Decoder("think", "passthrough", "passthrough"))

        await engine.detect(FakeModel(backend))

        assert engine.decoder.channel_scanner is _KNOWN_CHANNEL_SCANNERS["think"]
        assert isinstance(engine.decoder.tool_scanner, PassthroughScanner)
        assert backend.generate_calls == []
        assert backend.chat_template_sample_calls == 0

    async def test_detect_template_only_skips_preflight(self) -> None:
        backend = FakeLLMBackend(
            chunks=["unused"],
            chat_template_sample='<think>r</think><tool_call>{"name":"fn","arguments":{}}</tool_call>',
        )
        engine = LLMCodec(None)

        await engine.detect(FakeModel(backend))

        assert backend.chat_template_sample_calls == 1
        assert backend.generate_calls == []
        assert engine.decoder.channel_scanner is _KNOWN_CHANNEL_SCANNERS["think"]
        assert engine.decoder.tool_scanner is _KNOWN_TOOL_SCANNERS["tool_call"]
        assert isinstance(engine.decoder.tool_parser, JSONParser)

    async def test_detect_falls_back_to_preflight(self) -> None:
        backend = FakeLLMBackend(
            chunks=['<tool_call>{"name":"fn","arguments":{}}</tool_call>'],
            chat_template_sample="<think>r</think>",
        )
        engine = LLMCodec(None)

        await engine.detect(FakeModel(backend))

        assert backend.chat_template_sample_calls == 1
        assert len(backend.generate_calls) == 1
        assert engine.decoder.channel_scanner is _KNOWN_CHANNEL_SCANNERS["think"]
        assert engine.decoder.tool_scanner is _KNOWN_TOOL_SCANNERS["tool_call"]

    @pytest.mark.parametrize(
        ["spec", "chunks", "template", "expected_channel", "expected_tool", "expected_parser_type"],
        [
            pytest.param(
                Decoder(channel_scanner="think"),
                ["<|channel|>x<|message|>y<|end|>"],
                '<tool_call>{"name":"fn","arguments":{}}</tool_call>',
                _KNOWN_CHANNEL_SCANNERS["think"],
                _KNOWN_TOOL_SCANNERS["tool_call"],
                JSONParser,
                id="pinned_channel_detects_others",
            ),
            pytest.param(
                Decoder(tool_scanner="passthrough"),
                ["<think>r</think>"],
                '<tool_call>{"name":"fn","arguments":{}}</tool_call>',
                _KNOWN_CHANNEL_SCANNERS["think"],
                PassthroughScanner,
                PassthroughParser,
                id="pinned_passthrough_tool_constrains_parser",
            ),
            pytest.param(
                Decoder(tool_parser=JSONArrayParser()),
                ["plain output"],
                '<tool_call>{"name":"fn","arguments":{}}</tool_call>',
                None,
                _KNOWN_TOOL_SCANNERS["tool_call"],
                JSONArrayParser,
                id="pinned_parser_preserved",
            ),
        ],
    )
    async def test_detect_partial_auto_detect(
        self,
        spec: Decoder,
        chunks: list[str],
        template: str,
        expected_channel: Scanner | None,
        expected_tool: Scanner | type,
        expected_parser_type: type,
    ) -> None:
        backend = FakeLLMBackend(chunks=chunks, chat_template_sample=template)
        engine = LLMCodec(spec)

        await engine.detect(FakeModel(backend))

        if expected_channel is not None:
            assert engine.decoder.channel_scanner is expected_channel
        if isinstance(expected_tool, type):
            assert isinstance(engine.decoder.tool_scanner, expected_tool)
        else:
            assert engine.decoder.tool_scanner is expected_tool
        assert isinstance(engine.decoder.tool_parser, expected_parser_type)

    async def test_detect_warns_on_passthrough_fallback(self, caplog_flama: pytest.LogCaptureFixture) -> None:
        """Auto-detection that lands on the ``passthrough`` parser despite a real tool scanner emits
        a WARNING so operators know tool-calling endpoints (OpenAI/Ollama) will surface empty-named
        :class:`ToolEvent`s.
        """
        backend = FakeLLMBackend(
            chunks=["plain"], chat_template_sample='<tool_call>{"name":"fn","arguments":{}}</tool_call>'
        )
        engine = LLMCodec(Decoder(tool_parser=PassthroughParser()))

        with caplog_flama.at_level(logging.WARNING, logger="flama.models.engine.llm.codec"):
            await engine.detect(FakeModel(backend))

        assert engine.decoder.tool_parser.name == "passthrough"
        assert engine.decoder.tool_scanner.name != "passthrough"
        assert any("Tool parser fell back to 'passthrough'" in r.getMessage() for r in caplog_flama.records)

    async def test_detect_silent_when_scanner_also_passthrough(self, caplog_flama: pytest.LogCaptureFixture) -> None:
        """Native runs (no tool scanner) and explicit ``passthrough`` configurations stay silent —
        only the *unintentional* fallback case is worth a WARNING.
        """
        engine = LLMCodec(Decoder(tool_scanner="passthrough", tool_parser=PassthroughParser()))

        with caplog_flama.at_level(logging.WARNING, logger="flama.models.engine.llm.codec"):
            await engine.detect(FakeModel(FakeLLMBackend(chunks=["plain"], chat_template_sample="")))

        assert not any("Tool parser fell back to 'passthrough'" in r.getMessage() for r in caplog_flama.records)

    @pytest.mark.parametrize(
        ["backend", "expected"],
        [
            pytest.param(FakeLLMBackend(chat_template_sample="<think>r</think>"), "<think>r</think>", id="ok"),
            pytest.param(FakeLLMBackend(chat_template_sample=None), None, id="none"),
            pytest.param(
                FakeLLMBackend(raise_on_chat_template_sample=RuntimeError("boom")), None, id="raises_falls_back"
            ),
        ],
    )
    def test_chat_template_sample(self, backend: FakeLLMBackend, expected: str | None) -> None:
        engine = LLMCodec(None)

        assert engine._chat_template_sample(FakeModel(backend)) == expected

    def test_chat_template_sample_no_backend_returns_none(self) -> None:
        engine = LLMCodec(None)

        assert engine._chat_template_sample(FakeModel(None)) is None

    async def test_preflight_collects_sample_text(self) -> None:
        backend = FakeLLMBackend(chunks=["<think>r</think>"])
        engine = LLMCodec(None)

        result = await engine._preflight(FakeModel(backend))

        assert result == "<think>r</think>"
        assert backend.generate_calls
        assert backend.generate_calls[0][1].get("max_tokens") == PREFLIGHT_MAX_TOKENS

    async def test_preflight_returns_none_on_generate_error(self) -> None:
        backend = FakeLLMBackend(raise_on_generate=RuntimeError("boom"))
        engine = LLMCodec(None)

        assert await engine._preflight(FakeModel(backend)) is None

    async def test_preflight_returns_none_when_no_backend(self) -> None:
        engine = LLMCodec(None)

        assert await engine._preflight(FakeModel(None)) is None

    async def test_preflight_stops_at_max_chars(self) -> None:
        backend = FakeLLMBackend(chunks=["a" * (PREFLIGHT_MAX_CHARS + 16), "ignored-after-break"])
        engine = LLMCodec(None)

        result = await engine._preflight(FakeModel(backend))

        assert result is not None
        assert len(result) >= PREFLIGHT_MAX_CHARS
        assert "ignored-after-break" not in result

    async def test_detect_without_backend_skips_token_counter(self) -> None:
        engine = LLMCodec(None)

        await engine.detect(FakeModel(None))

        assert engine.decoder.tool_parser.name == "passthrough"
        assert engine.decoder.channel_scanner.name == "passthrough"

    async def test_decode_passthrough_chunks(self) -> None:
        engine = make_engine()

        items = await consume(engine.decode(aiter([EngineDelta(text="hi "), EngineDelta(text="there")])))

        assert items == [TextEvent(channel="output", text="hi "), TextEvent(channel="output", text="there")]

    @pytest.mark.parametrize(
        ["chunks", "channel_scanner", "expected_blocks"],
        [
            pytest.param(
                ["<think>r</think>output"],
                _THINK_SCANNER,
                [TextEvent(channel=None, text="r"), TextEvent(channel="output", text="output")],
                id="think",
            ),
            pytest.param(
                ["<|channel>analysis\nbody<channel|>final"],
                _CHANNEL_SCANNER,
                [TextEvent(channel="analysis", text="body"), TextEvent(channel="output", text="final")],
                id="channel_capture_inner",
            ),
            pytest.param(
                ["<|channel|>final<|message|>hi<|end|>more"],
                _HARMONY_SCANNER,
                [TextEvent(channel="final", text="hi"), TextEvent(channel="output", text="more")],
                id="harmony",
            ),
            pytest.param(
                ["<thi", "nk>r</think>"],
                _THINK_SCANNER,
                [TextEvent(channel=None, text="r")],
                id="partial_buffer_held",
            ),
        ],
    )
    async def test_decode_channel_scanners(
        self,
        chunks: list[str],
        channel_scanner: Scanner,
        expected_blocks: list[TextEvent],
    ) -> None:
        engine = make_engine(channel_scanner=channel_scanner)

        items = await consume(engine.decode(aiter([EngineDelta(text=c) for c in chunks])))

        assert [b for b in items if isinstance(b, TextEvent)] == expected_blocks

    @pytest.mark.parametrize(
        ["chunks", "tool_scanner", "tool_parser", "expected_names"],
        [
            pytest.param(
                ['<tool_call>{"name":"fn","arguments":{"x":1}}</tool_call>'],
                _TOOL_CALL_SCANNER,
                JSONObjectParser(),
                ["fn"],
                id="json_object",
            ),
            pytest.param(
                ['<|python_tag|>{"name":"a","arguments":{}}'],
                _PYTHON_TAG_SCANNER,
                JSONSequenceParser(separator="; "),
                ["a"],
                id="python_tag_remarker",
            ),
            pytest.param(
                ["[fn(a=1)]"], _PYTHONIC_SCANNER, PythonicParser(), ["fn"], id="pythonic_start_of_buffer_only"
            ),
            pytest.param(
                ['[TOOL_CALLS][{"name":"a","arguments":{}},{"name":"b","arguments":{}}]'],
                _KNOWN_TOOL_SCANNERS["tool_calls"],
                JSONArrayParser(),
                ["a", "b"],
                id="array_marker_yields_one_block_per_call",
            ),
            pytest.param(
                ["<tool_call>opaque body</tool_call>"],
                _TOOL_CALL_SCANNER,
                PassthroughParser(),
                [""],
                id="passthrough_parser",
            ),
        ],
    )
    async def test_decode_tool_scanners(
        self,
        chunks: list[str],
        tool_scanner: Scanner,
        tool_parser: ToolParser,
        expected_names: list[str],
    ) -> None:
        engine = make_engine(tool_scanner=tool_scanner, tool_parser=tool_parser)

        items = await consume(engine.decode(aiter([EngineDelta(text=c) for c in chunks])))

        assert [b.name for b in items if isinstance(b, ToolEvent)] == expected_names

    async def test_decode_tool_block_id_is_canonical_uuid(self) -> None:
        deterministic = uuid.UUID("00000000-0000-0000-0000-000000000001")
        engine = make_engine(tool_scanner=_TOOL_CALL_SCANNER, tool_parser=JSONObjectParser())

        with patch("flama.models.engine.llm.codec.uuid.uuid4", return_value=deterministic):
            items = await consume(
                engine.decode(aiter([EngineDelta(text='<tool_call>{"name":"fn","arguments":{}}</tool_call>')]))
            )

        tool_blocks = [b for b in items if isinstance(b, ToolEvent)]
        assert tool_blocks[0].id == str(deterministic)

    async def test_decode_pythonic_off_buffer_treats_text_as_content(self) -> None:
        engine = make_engine(tool_scanner=_PYTHONIC_SCANNER, tool_parser=PythonicParser())

        items = await consume(engine.decode(aiter([EngineDelta(text="text [fn(a=1)]")])))

        assert [b for b in items if isinstance(b, TextEvent)][0].text.startswith("text ")

    async def test_decode_passthrough_tool_scanner_with_known_parser(self) -> None:
        engine = make_engine(tool_scanner=PassthroughScanner(), tool_parser=JSONObjectParser())

        items = await consume(engine.decode(aiter([EngineDelta(text='<tool_call>{"name":"x"}</tool_call>')])))

        assert [b for b in items if isinstance(b, TextEvent)] == [
            TextEvent(channel="output", text='<tool_call>{"name":"x"}</tool_call>')
        ]

    async def test_decode_unclosed_channel_flushed_on_eos(self) -> None:
        engine = make_engine(channel_scanner=_THINK_SCANNER)

        items = await consume(engine.decode(aiter([EngineDelta(text="<think>tail")])))

        assert any(isinstance(b, TextEvent) and b.text == "tail" and b.channel is None for b in items)

    async def test_decode_flushes_held_partial_marker_on_eos(self) -> None:
        """A trailing partial open-marker prefix held back by the scanner must be flushed as plain
        text at EOS rather than being silently dropped.
        """
        engine = make_engine(channel_scanner=_THINK_SCANNER)

        items = await consume(engine.decode(aiter([EngineDelta(text="hello <thi")])))

        text = "".join(b.text for b in items if isinstance(b, TextEvent))
        assert text == "hello <thi"

    @pytest.mark.parametrize(
        ["chunks", "expected_output", "expected_thought"],
        [
            pytest.param(
                ["<channel|>The answer is 42."],
                "The answer is 42.",
                "",
                id="stray_close_at_buffer_start",
            ),
            pytest.param(
                ["The answer is <channel|> 42."],
                "The answer is  42.",
                "",
                id="stray_close_mid_content",
            ),
            pytest.param(
                ["the answer is <chann", "el|>tail"],
                "the answer is tail",
                "",
                id="partial_close_split_across_deltas",
            ),
            pytest.param(
                ["<|channel>thought\n<channel|>The answer is 42."],
                "The answer is 42.",
                "",
                id="empty_thought_pair_then_content",
            ),
            pytest.param(
                ["<|channel>thought\nLet me think.\n<channel|>The answer is 42."],
                "The answer is 42.",
                "Let me think.\n",
                id="thought_block_then_content",
            ),
        ],
    )
    async def test_decode_channel_scanner_strips_stray_close_marker(
        self, chunks: list[str], expected_output: str, expected_thought: str
    ) -> None:
        """Stray ``<channel|>`` literals (Gemma 4 prompt-prefix artifact) must never leak to the output channel."""
        engine = make_engine(channel_scanner=_CHANNEL_SCANNER)

        items = await consume(engine.decode(aiter([EngineDelta(text=c) for c in chunks])))

        text_blocks = [b for b in items if isinstance(b, TextEvent)]
        assert "".join(b.text for b in text_blocks if b.channel == "output") == expected_output
        assert "".join(b.text for b in text_blocks if b.channel == "thought") == expected_thought
        for b in text_blocks:
            assert "<channel|>" not in b.text
            assert "<|channel>" not in b.text

    async def test_decode_unclosed_tool_flushed_on_eos(self) -> None:
        engine = make_engine(tool_scanner=_TOOL_CALL_SCANNER, tool_parser=JSONObjectParser())

        items = await consume(engine.decode(aiter([EngineDelta(text='<tool_call>{"name":"fn","arguments":{}}')])))

        tool_blocks = [b for b in items if isinstance(b, ToolEvent)]
        assert tool_blocks[-1].name == "fn"

    async def test_decode_flushes_held_tool_partial_close_on_eos(self) -> None:
        """A trailing partial close-marker prefix held while inside a tool body must be folded back
        into the tool buffer at EOS so the parked tool call is still drained.
        """
        engine = make_engine(tool_scanner=_TOOL_CALL_SCANNER, tool_parser=PassthroughParser())

        items = await consume(
            engine.decode(aiter([EngineDelta(text="<tool_call>opaque"), EngineDelta(text="</tool_cal")]))
        )

        assert any(isinstance(b, ToolEvent) for b in items)

    async def test_decode_tool_wins_over_channel_on_tie(self) -> None:
        engine = make_engine(
            channel_scanner=_THINK_SCANNER, tool_scanner=_TOOL_CALL_SCANNER, tool_parser=PassthroughParser()
        )

        items = await consume(engine.decode(aiter([EngineDelta(text="<tool_call>{}</tool_call>")])))

        assert any(isinstance(b, ToolEvent) for b in items)

    async def test_decode_tool_inside_channel_restores_channel(self) -> None:
        engine = make_engine(
            channel_scanner=_THINK_SCANNER, tool_scanner=_TOOL_CALL_SCANNER, tool_parser=PassthroughParser()
        )

        items = await consume(
            engine.decode(aiter([EngineDelta(text="<think>before<tool_call>{}</tool_call>after</think>tail")]))
        )

        text_blocks = [b for b in items if isinstance(b, TextEvent)]
        assert any(b.channel is None and b.text == "before" for b in text_blocks)
        assert any(b.channel is None and b.text == "after" for b in text_blocks)
        assert any(b.channel == "output" and b.text == "tail" for b in text_blocks)

    async def test_decode_propagates_trace_metadata(self) -> None:
        engine = make_engine()

        items = await consume(
            engine.decode(
                aiter(
                    [
                        EngineDelta(text="hi", token_count=1),
                        EngineDelta(text=" there", token_count=2),
                        EngineDelta(text="", token_count=2, finish_reason="stop"),
                    ]
                )
            )
        )

        blocks = [item for item in items if isinstance(item, TextEvent)]
        traces = [item for item in items if isinstance(item, TraceEvent)]
        assert blocks == [TextEvent(channel="output", text="hi"), TextEvent(channel="output", text=" there")]
        assert traces == [
            TraceEvent(token_count=1),
            TraceEvent(token_count=2),
            TraceEvent(token_count=2, finish_reason="stop"),
        ]

    async def test_decode_unclosed_tool_flushed_before_terminal_trace(self) -> None:
        engine = make_engine(tool_scanner=_TOOL_CALL_SCANNER, tool_parser=JSONObjectParser())

        items = await consume(
            engine.decode(
                aiter(
                    [
                        EngineDelta(text='<tool_call>{"name":"fn","arguments":{}}'),
                        EngineDelta(text="", token_count=10, finish_reason="stop"),
                    ]
                )
            )
        )

        kinds = [type(item).__name__ for item in items]
        assert kinds[-2:] == ["ToolEvent", "TraceEvent"]
        assert isinstance(items[-1], TraceEvent)
        assert items[-1].finish_reason == "stop"

    @pytest.mark.parametrize(
        ["delta", "encoder_raises", "expected_traces", "expects_debug_log"],
        [
            pytest.param(
                EngineDelta(text="hi"),
                False,
                [TraceEvent(token_count=3)],
                False,
                id="applies_when_count_none",
            ),
            pytest.param(
                EngineDelta(text="hi", token_count=42),
                False,
                [TraceEvent(token_count=42)],
                False,
                id="preserves_explicit_count",
            ),
            pytest.param(
                EngineDelta(text="", finish_reason="stop"),
                False,
                [TraceEvent(token_count=None, finish_reason="stop")],
                False,
                id="skips_for_empty_text",
            ),
            pytest.param(
                EngineDelta(text="hi"),
                True,
                [],
                True,
                id="swallows_encoder_exception",
            ),
        ],
    )
    async def test_decode_token_counter_fallback(
        self,
        fake_backend: FakeLLMBackend,
        delta: EngineDelta,
        encoder_raises: bool,
        expected_traces: list[TraceEvent],
        expects_debug_log: bool,
        caplog_flama: pytest.LogCaptureFixture,
    ) -> None:
        """Cover the ``token_count`` fallback path wired by :meth:`LLMCodec.detect`.

        ``detect`` captures the backend's ``encode`` primitive so :meth:`LLMCodec.decode` can
        recover a count for deltas that arrive with ``token_count=None``. The fallback is gated:
        explicit counts are preserved (no double-counting on vLLM / recent MLX), empty-text
        deltas are left alone (terminal frames carry only ``finish_reason``), and a misbehaving
        tokenizer (e.g. raising on partial UTF-8) is swallowed at debug level so the stream
        keeps flowing. Each scenario is detectable from the resulting :class:`TraceEvent`s alone:
        the FSM emits a trace whenever ``token_count`` or ``finish_reason`` is set on the delta,
        which transitively proves the rewrite happened (or didn't)."""
        if encoder_raises:

            def _raise(text: str, *, add_special_tokens: bool = True) -> list[int]:
                raise RuntimeError("partial utf-8")

            fake_backend.encode = _raise  # type: ignore[method-assign]

        engine = LLMCodec(None)
        await engine.detect(FakeModel(fake_backend))

        with caplog_flama.at_level(logging.DEBUG, logger="flama.models.engine.llm.codec"):
            items = await consume(engine.decode(aiter([delta])))

        traces = [item for item in items if isinstance(item, TraceEvent)]
        assert traces == expected_traces
        assert ("Token-count fallback raised" in caplog_flama.text) is expects_debug_log
