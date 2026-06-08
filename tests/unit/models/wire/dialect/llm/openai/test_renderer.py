import json
import typing as t
import uuid

import pytest

from flama.http.responses.sse import ServerSentEvent
from flama.models.transport.output.llm.buffer import EventBuffer
from flama.models.transport.output.llm.event import Event as TransportEvent
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent
from flama.models.wire.dialect.llm.openai.renderer import OpenAIRenderer

_GENERATION_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def _decode(frame: ServerSentEvent) -> dict[str, t.Any]:
    return json.loads(frame.data)


def _delta(frame: ServerSentEvent) -> dict[str, t.Any]:
    if frame.data == "[DONE]":
        return {}
    return _decode(frame)["choices"][0].get("delta", {})


_Driver = t.Callable[[], t.Awaitable[list[ServerSentEvent]]]


def _build_driver(
    blocks: list[TransportEvent],
    *,
    api: t.Literal["chat", "completion", "response"],
    model: str = "m",
    generation_id: uuid.UUID | None = _GENERATION_ID,
    skip: int | None = None,
) -> _Driver:
    async def _driver() -> list[ServerSentEvent]:
        renderer = OpenAIRenderer(api=api, model=model, generation_id=generation_id)
        if skip is not None:
            renderer.skip = skip
        return [frame async for frame in EventBuffer(blocks, renderer)]

    return _driver


_PREFIX_EVENTS: list[TransportEvent] = [
    StartEvent(id="m", created=0),
    TextEvent(channel="output", text="hi"),
    StopEvent(stop_reason="stop"),
]


def _verify_chat_init_empty(frames: list[ServerSentEvent]) -> None:
    assert frames == []


def _verify_chat_full_sequence(frames: list[ServerSentEvent]) -> None:
    assert _delta(frames[0]) == {"role": "assistant"}
    assert _delta(frames[1]) == {"content": "hi"}
    assert _delta(frames[2]) == {"content": " there"}
    assert _decode(frames[-2])["choices"][0]["finish_reason"] == "stop"
    assert frames[-1].data == "[DONE]"


def _verify_chat_envelope_object_and_model(frames: list[ServerSentEvent]) -> None:
    body = _decode(frames[0])
    assert body["object"] == "chat.completion.chunk"
    assert body["model"] == "qwen"


def _verify_chat_role_emitted_once(frames: list[ServerSentEvent]) -> None:
    role_frames = [f for f in frames if _delta(f) == {"role": "assistant"}]
    assert len(role_frames) == 1


def _verify_chat_tool_call_emits_tool_chunk(frames: list[ServerSentEvent]) -> None:
    tool_frames = [f for f in frames if "tool_calls" in _delta(f)]
    assert len(tool_frames) == 1
    tool_call = _delta(tool_frames[0])["tool_calls"][0]
    assert tool_call == {
        "index": 0,
        "id": "c1",
        "type": "function",
        "function": {"name": "lookup", "arguments": json.dumps({"q": "x"})},
    }
    terminal = next(f for f in frames if _decode(f)["choices"][0]["finish_reason"] == "tool_calls")
    assert _decode(terminal)["choices"][0]["finish_reason"] == "tool_calls"


def _verify_chat_multiple_tool_calls(frames: list[ServerSentEvent]) -> None:
    tool_frames = [f for f in frames if "tool_calls" in _delta(f)]
    indices = [_delta(f)["tool_calls"][0]["index"] for f in tool_frames]
    assert indices == [0, 1]


def _verify_chat_drops_unparseable_tool_block(frames: list[ServerSentEvent]) -> None:
    assert not any("tool_calls" in _delta(f) for f in frames if f.data != "[DONE]")


def _verify_chat_off_output_routes_to_reasoning_content(frames: list[ServerSentEvent]) -> None:
    delta_frames = [f for f in frames if "content" in _delta(f) or "reasoning_content" in _delta(f)]
    assert [_delta(f) for f in delta_frames] == [
        {"reasoning_content": "thinking "},
        {"reasoning_content": "aloud"},
        {"content": "answer"},
    ]


def _verify_chat_thinking_skipped_when_empty(frames: list[ServerSentEvent]) -> None:
    delta_frames = [f for f in frames if "content" in _delta(f) or "reasoning_content" in _delta(f)]
    assert [_delta(f) for f in delta_frames] == [{"content": "answer"}]


def _verify_chat_suppresses_empty_text(frames: list[ServerSentEvent]) -> None:
    content_frames = [f for f in frames if "content" in _delta(f)]
    assert content_frames == []


def _verify_chat_error_stop_emits_error_envelope(frames: list[ServerSentEvent]) -> None:
    body_frames = [f for f in frames if f.data != "[DONE]"]
    error_frames = [f for f in body_frames if "error" in _decode(f)]
    assert len(error_frames) == 1
    assert _decode(error_frames[0])["error"] == {
        "message": "LLM stream generation failed",
        "type": "internal_error",
        "code": 500,
    }
    terminal = next(_decode(f) for f in body_frames if _decode(f)["choices"][0]["finish_reason"] is not None)
    assert terminal["choices"][0]["finish_reason"] == "stop"
    assert frames[-1].data == "[DONE]"


def _make_chat_stop_reason_verifier(expected_finish: str) -> t.Callable[[list[ServerSentEvent]], None]:
    def _verify(frames: list[ServerSentEvent]) -> None:
        body_frames = [f for f in frames if f.data != "[DONE]"]
        terminal = next(f for f in body_frames if _decode(f)["choices"][0]["finish_reason"] is not None)
        assert _decode(terminal)["choices"][0]["finish_reason"] == expected_finish

    return _verify


def _verify_completion_text_delta(frames: list[ServerSentEvent]) -> None:
    body_frames = [f for f in frames if f.data != "[DONE]"]
    assert _decode(body_frames[0])["object"] == "text_completion"
    assert _decode(body_frames[0])["choices"] == [{"index": 0, "text": "hello", "finish_reason": None}]
    assert _decode(body_frames[-1])["choices"] == [{"index": 0, "text": "", "finish_reason": "stop"}]
    assert frames[-1].data == "[DONE]"


def _verify_completion_drops_thinking_channel(frames: list[ServerSentEvent]) -> None:
    text_frames = [f for f in frames if f.data != "[DONE]" and _decode(f)["choices"][0].get("text")]
    assert [_decode(f)["choices"][0]["text"] for f in text_frames] == ["visible"]


def _verify_completion_ignores_tool_blocks(frames: list[ServerSentEvent]) -> None:
    assert not any("tool_calls" in str(f.data) for f in frames)


def _verify_response_structured_reasoning(frames: list[ServerSentEvent]) -> None:
    events = [f.event for f in frames]
    assert "response.created" in events
    assert "response.reasoning_summary_text.delta" in events
    assert "response.output_text.delta" in events
    assert "response.completed" in events


def _verify_response_completed_carries_usage(frames: list[ServerSentEvent]) -> None:
    completed = next(f for f in frames if f.event == "response.completed")
    assert _decode(completed)["response"]["usage"] == {
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
    }


def _verify_response_id_carries_resp_prefix(frames: list[ServerSentEvent]) -> None:
    created = next(f for f in frames if f.event == "response.created")
    assert _decode(created)["response"]["id"].startswith("resp-")


def _verify_response_error_stop_emits_failed(frames: list[ServerSentEvent]) -> None:
    failed = [f for f in frames if f.event == "response.failed"]
    assert len(failed) == 1
    body = _decode(failed[0])
    assert body["response"]["status"] == "failed"
    assert body["response"]["error"] == {
        "message": "LLM stream generation failed",
        "type": "internal_error",
        "code": 500,
    }


def _verify_response_tool_call(frames: list[ServerSentEvent]) -> None:
    events = [f.event for f in frames]
    assert "response.output_item.added" in events
    assert "response.function_call_arguments.delta" in events
    assert "response.function_call_arguments.done" in events
    assert "response.output_item.done" in events
    delta = next(f for f in frames if f.event == "response.function_call_arguments.delta")
    assert _decode(delta)["delta"] == json.dumps({"q": "x"})


def _verify_response_empty_text_suppressed(frames: list[ServerSentEvent]) -> None:
    assert "response.output_text.delta" not in [f.event for f in frames]


def _verify_response_tool_without_name_skipped(frames: list[ServerSentEvent]) -> None:
    assert "response.function_call_arguments.delta" not in [f.event for f in frames]


def _verify_response_reasoning_single_item(frames: list[ServerSentEvent]) -> None:
    added = [
        f
        for f in frames
        if f.event == "response.output_item.added" and _decode(f)["item"].get("type") == "reasoning"
    ]
    assert len(added) == 1
    deltas = [_decode(f)["delta"] for f in frames if f.event == "response.reasoning_summary_text.delta"]
    assert deltas == ["a", "b"]


def _make_envelope_id_prefix_verifier(
    api: t.Literal["chat", "completion", "response"], expected_prefix: str
) -> t.Callable[[list[ServerSentEvent]], None]:
    def _verify(frames: list[ServerSentEvent]) -> None:
        body_frames = [f for f in frames if f.data != "[DONE]"]
        body = _decode(body_frames[0])
        if api in ("chat", "completion"):
            assert body["id"].startswith(expected_prefix)
            assert body["id"].endswith(_GENERATION_ID.hex)
        else:
            assert body["response"]["id"].startswith(expected_prefix)
            assert body["response"]["id"].endswith(_GENERATION_ID.hex)

    return _verify


def _verify_skip_drops_leading_chunks(frames: list[ServerSentEvent]) -> None:
    assert frames[-1].data == "[DONE]"
    assert not any(_delta(f) == {"role": "assistant"} for f in frames if f.data != "[DONE]")


class TestCaseOpenAIRenderer:
    """Cover :class:`OpenAIRenderer` end-to-end across the three ``api`` modes (``chat``,
    ``completion``, ``response``) and the engine-driven :attr:`Renderer.skip` suppression hook.

    Each ``api`` selects an internal FSM strategy with its own envelope shape; the parametrized
    rows in :meth:`test_render` exhaust the per-mode behaviour, the per-stream identity prefix
    (``chatcmpl-`` / ``cmpl-`` / ``resp-`` anchored to a generation UUID), the stop-reason
    mapping for ``chat`` mode, and the engine's leading-frame suppression hook.
    """

    @pytest.mark.parametrize(
        ["driver", "verify"],
        [
            pytest.param(
                _build_driver(_PREFIX_EVENTS, api="chat"),
                _make_envelope_id_prefix_verifier("chat", "chatcmpl-"),
                id="chat_envelope_id_prefix",
            ),
            pytest.param(
                _build_driver(_PREFIX_EVENTS, api="completion"),
                _make_envelope_id_prefix_verifier("completion", "cmpl-"),
                id="completion_envelope_id_prefix",
            ),
            pytest.param(
                _build_driver(_PREFIX_EVENTS, api="response"),
                _make_envelope_id_prefix_verifier("response", "resp-"),
                id="response_envelope_id_prefix",
            ),
            pytest.param(
                _build_driver([], api="chat"),
                _verify_chat_init_empty,
                id="chat_init_empty",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=10),
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
                _build_driver([StartEvent(id="m", created=0)], api="chat", model="qwen"),
                _verify_chat_envelope_object_and_model,
                id="chat_envelope_carries_object_and_model",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        StartEvent(id="m2", created=1),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="chat",
                ),
                _verify_chat_role_emitted_once,
                id="chat_role_emitted_once",
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
                _verify_chat_tool_call_emits_tool_chunk,
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
                id="chat_multiple_tool_calls_increment_index",
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
                _build_driver(
                    [
                        TextEvent(channel="thinking", text="thinking "),
                        TextEvent(channel="thinking", text="aloud"),
                        TextEvent(channel="output", text="answer"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="chat",
                ),
                _verify_chat_off_output_routes_to_reasoning_content,
                id="chat_off_output_channel_routes_to_reasoning_content",
            ),
            pytest.param(
                _build_driver(
                    [
                        TextEvent(channel="thinking", text=""),
                        TextEvent(channel="output", text="answer"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="chat",
                ),
                _verify_chat_thinking_skipped_when_empty,
                id="chat_thinking_skipped_when_empty",
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
                _verify_chat_error_stop_emits_error_envelope,
                id="chat_error_stop_emits_error_envelope",
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
                _make_chat_stop_reason_verifier("tool_calls"),
                id="chat_stop_reason_tool_use",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="content_filter")], api="chat"),
                _make_chat_stop_reason_verifier("content_filter"),
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
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hello"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="completion",
                ),
                _verify_completion_text_delta,
                id="completion_text_delta_uses_text_completion_envelope",
            ),
            pytest.param(
                _build_driver(
                    [
                        TextEvent(channel="thinking", text="hidden"),
                        TextEvent(channel="output", text="visible"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="completion",
                ),
                _verify_completion_drops_thinking_channel,
                id="completion_drops_thinking_channel",
            ),
            pytest.param(
                _build_driver(
                    [ToolEvent(id="c1", name="f", arguments={}), StopEvent(stop_reason="stop")],
                    api="completion",
                ),
                _verify_completion_ignores_tool_blocks,
                id="completion_ignores_tool_blocks",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="thinking", text="thought"),
                        TextEvent(channel="output", text="answer"),
                        StopEvent(stop_reason="stop", output_tokens=2),
                    ],
                    api="response",
                ),
                _verify_response_structured_reasoning,
                id="response_structured_reasoning_emits_named_events",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0, input_tokens=2),
                        TextEvent(channel="output", text="x"),
                        StopEvent(stop_reason="stop", output_tokens=3),
                    ],
                    api="response",
                ),
                _verify_response_completed_carries_usage,
                id="response_completed_carries_usage",
            ),
            pytest.param(
                _build_driver([StartEvent(id="m", created=0)], api="response"),
                _verify_response_id_carries_resp_prefix,
                id="response_id_carries_resp_prefix",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="error")], api="response"),
                _verify_response_error_stop_emits_failed,
                id="response_error_stop_emits_response_failed",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        ToolEvent(id="c1", name="lookup", arguments={"q": "x"}),
                        StopEvent(stop_reason="tool_use"),
                    ],
                    api="response",
                ),
                _verify_response_tool_call,
                id="response_tool_call_emits_function_call_events",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text=""),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="response",
                ),
                _verify_response_empty_text_suppressed,
                id="response_suppresses_empty_text",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        ToolEvent(id="c1", name="", arguments={}),
                        StopEvent(stop_reason="tool_use"),
                    ],
                    api="response",
                ),
                _verify_response_tool_without_name_skipped,
                id="response_tool_without_name_skipped",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="thinking", text="a"),
                        TextEvent(channel="thinking", text="b"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="response",
                ),
                _verify_response_reasoning_single_item,
                id="response_reasoning_coalesces_single_item",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hi"),
                        StopEvent(stop_reason="stop"),
                    ],
                    api="chat",
                    skip=2,
                ),
                _verify_skip_drops_leading_chunks,
                id="skip_drops_leading_chunks",
            ),
        ],
    )
    async def test_render(
        self,
        driver: _Driver,
        verify: t.Callable[[list[ServerSentEvent]], None],
    ) -> None:
        frames = await driver()

        verify(frames)
