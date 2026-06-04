import typing as t

import pytest

from flama.models.transport.output.llm.buffer import EventBuffer
from flama.models.transport.output.llm.event import Event as TransportEvent
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent
from flama.models.wire.dialect.llm.ollama.renderer import OllamaRenderer

_Driver = t.Callable[[], t.Awaitable[list[dict[str, t.Any]]]]


def _build_driver(
    blocks: list[TransportEvent],
    *,
    api: t.Literal["chat", "generate"],
    model: str = "m",
    skip: int | None = None,
) -> _Driver:
    async def _driver() -> list[dict[str, t.Any]]:
        renderer = OllamaRenderer(api=api, model=model)
        if skip is not None:
            renderer.skip = skip
        return [frame async for frame in EventBuffer(blocks, renderer)]

    return _driver


def _verify_chat_init_empty(frames: list[dict[str, t.Any]]) -> None:
    assert frames == []


def _verify_chat_full_sequence(frames: list[dict[str, t.Any]]) -> None:
    assert frames[0]["message"] == {"role": "assistant", "content": "hi"}
    assert frames[0]["done"] is False
    assert frames[1]["message"] == {"role": "assistant", "content": " there"}
    assert frames[-1]["done"] is True
    assert frames[-1]["done_reason"] == "stop"
    assert frames[-1]["prompt_eval_count"] == 2
    assert frames[-1]["eval_count"] == 5
    assert frames[-1]["message"] == {"role": "assistant", "content": ""}


def _verify_chat_envelope_carries_model_and_created_at(frames: list[dict[str, t.Any]]) -> None:
    for frame in frames:
        assert frame["model"] == "qwen"
        assert "created_at" in frame


def _verify_chat_tool_call(frames: list[dict[str, t.Any]]) -> None:
    tool_frames = [f for f in frames if "tool_calls" in f.get("message", {})]
    assert len(tool_frames) == 1
    assert tool_frames[0]["message"]["tool_calls"] == [{"function": {"name": "lookup", "arguments": {"q": "x"}}}]


def _verify_chat_multiple_tool_calls(frames: list[dict[str, t.Any]]) -> None:
    tool_frames = [f for f in frames if "tool_calls" in f.get("message", {})]
    assert len(tool_frames) == 2
    assert tool_frames[0]["message"]["tool_calls"][0]["function"]["name"] == "a"
    assert tool_frames[1]["message"]["tool_calls"][0]["function"]["name"] == "b"


def _verify_chat_drops_unparseable_tool_block(frames: list[dict[str, t.Any]]) -> None:
    assert not any("tool_calls" in f.get("message", {}) for f in frames)


def _verify_chat_routes_non_output_into_thinking(frames: list[dict[str, t.Any]]) -> None:
    thinking_frames = [f for f in frames if not f.get("done") and f.get("message", {}).get("thinking")]
    output_frames = [f for f in frames if not f.get("done") and f.get("message", {}).get("content")]
    assert [f["message"]["thinking"] for f in thinking_frames] == ["hidden"]
    assert [f["message"]["content"] for f in output_frames] == ["visible"]


def _verify_chat_suppresses_empty_text(frames: list[dict[str, t.Any]]) -> None:
    delta_frames = [f for f in frames if not f.get("done") and f["message"]["content"]]
    assert delta_frames == []


def _verify_chat_error_stop_emits_error_frame(frames: list[dict[str, t.Any]]) -> None:
    error_frames = [f for f in frames if "error" in f]
    assert len(error_frames) == 1
    assert error_frames[0] == {"error": "LLM stream generation failed"}
    terminal = frames[-1]
    assert terminal["done"] is True
    assert terminal["done_reason"] == "stop"


def _make_chat_stop_reason_verifier(expected_done: str) -> t.Callable[[list[dict[str, t.Any]]], None]:
    def _verify(frames: list[dict[str, t.Any]]) -> None:
        assert frames[-1]["done_reason"] == expected_done

    return _verify


def _verify_chat_trace_accumulates_output_tokens(frames: list[dict[str, t.Any]]) -> None:
    assert frames[-1]["prompt_eval_count"] == 1
    assert frames[-1]["eval_count"] == 5


def _verify_generate_full_sequence(frames: list[dict[str, t.Any]]) -> None:
    delta_frames = [f for f in frames if not f.get("done")]
    assert [f["response"] for f in delta_frames] == ["hello"]
    assert frames[-1]["done"] is True
    assert frames[-1]["response"] == ""


def _verify_generate_drops_non_output_channels(frames: list[dict[str, t.Any]]) -> None:
    delta_frames = [f for f in frames if not f.get("done") and f.get("response")]
    assert [f["response"] for f in delta_frames] == ["visible"]


def _verify_generate_ignores_tool_blocks(frames: list[dict[str, t.Any]]) -> None:
    assert not any("tool_calls" in f.get("message", {}) for f in frames if "message" in f)


def _verify_skip_drops_leading_frames(frames: list[dict[str, t.Any]]) -> None:
    deltas = [f for f in frames if not f.get("done") and f["message"]["content"]]
    assert deltas == []
    assert frames[-1]["done"] is True


def _make_routes_non_output_driver(channel: str | None) -> _Driver:
    return _build_driver(
        [
            TextEvent(channel=channel, text="hidden"),
            TextEvent(channel="output", text="visible"),
            StopEvent(stop_reason="stop"),
        ],
        api="chat",
    )


class TestCaseOllamaRenderer:
    """Cover :class:`OllamaRenderer` for both ``/api/chat`` and ``/api/generate`` envelopes,
    including stop-reason mapping, channel routing, trace accumulation, and the engine-driven
    leading-frame suppression (``Renderer.skip``).
    """

    @pytest.mark.parametrize(
        ["driver", "verify"],
        [
            pytest.param(_build_driver([], api="chat"), _verify_chat_init_empty, id="chat_init_empty"),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=10, input_tokens=2),
                        TextEvent(channel="output", text="hi"),
                        TextEvent(channel="output", text=" there"),
                        TraceEvent(token_count=5),
                        StopEvent(stop_reason="stop", output_tokens=5),
                    ],
                    api="chat",
                ),
                _verify_chat_full_sequence,
                id="chat_full_sequence",
            ),
            pytest.param(
                _build_driver(
                    [TextEvent(channel="output", text="hi"), StopEvent(stop_reason="stop")],
                    api="chat",
                    model="qwen",
                ),
                _verify_chat_envelope_carries_model_and_created_at,
                id="chat_envelope_carries_model_and_created_at",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        ToolEvent(id="c1", name="lookup", arguments={"q": "x"}),
                        StopEvent(stop_reason="tool_use"),
                    ],
                    api="chat",
                ),
                _verify_chat_tool_call,
                id="chat_tool_call_emits_tool_chunk",
            ),
            pytest.param(
                _build_driver(
                    [
                        ToolEvent(id="c1", name="a", arguments={}),
                        ToolEvent(id="c2", name="b", arguments={}),
                        StopEvent(stop_reason="tool_use"),
                    ],
                    api="chat",
                ),
                _verify_chat_multiple_tool_calls,
                id="chat_multiple_tool_calls_emit_separate_frames",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        ToolEvent(id="raw-body", name="", arguments={}),
                        StopEvent(stop_reason="tool_use"),
                    ],
                    api="chat",
                ),
                _verify_chat_drops_unparseable_tool_block,
                id="chat_drops_unparseable_tool_block",
            ),
            pytest.param(
                _make_routes_non_output_driver("thinking"),
                _verify_chat_routes_non_output_into_thinking,
                id="chat_routes_named_thinking_into_thinking",
            ),
            pytest.param(
                _make_routes_non_output_driver("analysis"),
                _verify_chat_routes_non_output_into_thinking,
                id="chat_routes_named_analysis_into_thinking",
            ),
            pytest.param(
                _make_routes_non_output_driver(None),
                _verify_chat_routes_non_output_into_thinking,
                id="chat_routes_unnamed_capture_into_thinking",
            ),
            pytest.param(
                _build_driver(
                    [TextEvent(channel="output", text=""), StopEvent(stop_reason="stop")],
                    api="chat",
                ),
                _verify_chat_suppresses_empty_text,
                id="chat_suppresses_empty_text",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="error")], api="chat"),
                _verify_chat_error_stop_emits_error_frame,
                id="chat_error_stop_emits_error_frame",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="stop")], api="chat"),
                _make_chat_stop_reason_verifier("stop"),
                id="chat_stop_reason_stop",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="max_tokens")], api="chat"),
                _make_chat_stop_reason_verifier("length"),
                id="chat_stop_reason_max_tokens",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="tool_use")], api="chat"),
                _make_chat_stop_reason_verifier("stop"),
                id="chat_stop_reason_tool_use",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="content_filter")], api="chat"),
                _make_chat_stop_reason_verifier("stop"),
                id="chat_stop_reason_content_filter",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="cancelled")], api="chat"),
                _make_chat_stop_reason_verifier("stop"),
                id="chat_stop_reason_cancelled",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="error")], api="chat"),
                _make_chat_stop_reason_verifier("stop"),
                id="chat_stop_reason_error",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="unknown")], api="chat"),
                _make_chat_stop_reason_verifier("stop"),
                id="chat_stop_reason_unknown",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason=None)], api="chat"),
                _make_chat_stop_reason_verifier("stop"),
                id="chat_stop_reason_none",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0, input_tokens=1),
                        TraceEvent(token_count=3),
                        TraceEvent(token_count=2),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="chat",
                ),
                _verify_chat_trace_accumulates_output_tokens,
                id="chat_trace_blocks_accumulate_output_tokens",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hello"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="generate",
                ),
                _verify_generate_full_sequence,
                id="generate_full_sequence",
            ),
            pytest.param(
                _build_driver(
                    [
                        TextEvent(channel="thinking", text="hidden"),
                        TextEvent(channel="output", text="visible"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="generate",
                ),
                _verify_generate_drops_non_output_channels,
                id="generate_drops_non_output_channels",
            ),
            pytest.param(
                _build_driver(
                    [
                        ToolEvent(id="c1", name="f", arguments={}),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="generate",
                ),
                _verify_generate_ignores_tool_blocks,
                id="generate_ignores_tool_blocks",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hi"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="chat",
                    skip=1,
                ),
                _verify_skip_drops_leading_frames,
                id="skip_drops_leading_frames",
            ),
        ],
    )
    async def test_render(
        self,
        driver: _Driver,
        verify: t.Callable[[list[dict[str, t.Any]]], None],
    ) -> None:
        frames = await driver()

        verify(frames)
