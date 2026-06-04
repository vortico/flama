import json
import typing as t
import uuid

import pytest

from flama.http.responses.sse import ServerSentEvent
from flama.models.transport.output.llm.buffer import EventBuffer
from flama.models.transport.output.llm.event import Event as TransportEvent
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect.llm.anthropic.renderer import AnthropicRenderer

_GENERATION_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def _decode(frame: ServerSentEvent) -> dict[str, t.Any]:
    return json.loads(frame.data)


_Driver = t.Callable[[], t.Awaitable[list[ServerSentEvent]]]


def _build_driver(
    blocks: list[TransportEvent],
    *,
    model: str = "m",
    generation_id: uuid.UUID | None = _GENERATION_ID,
    skip: int | None = None,
) -> _Driver:
    async def _driver() -> list[ServerSentEvent]:
        renderer = AnthropicRenderer(model=model, generation_id=generation_id)
        if skip is not None:
            renderer.skip = skip
        return [frame async for frame in EventBuffer(blocks, renderer)]

    return _driver


def _events_of(frames: list[ServerSentEvent]) -> list[str | None]:
    return [f.event for f in frames]


def _verify_message_envelope_id_prefix(frames: list[ServerSentEvent]) -> None:
    started = next(f for f in frames if f.event == "message_start")
    body = _decode(started)
    assert body["message"]["id"].startswith("msg_")
    assert body["message"]["id"].endswith(_GENERATION_ID.hex)
    assert body["message"]["model"] == "m"
    assert body["message"]["role"] == "assistant"


def _verify_text_block_lifecycle(frames: list[ServerSentEvent]) -> None:
    events = _events_of(frames)
    assert events[0] == "message_start"
    assert "content_block_start" in events
    assert "content_block_delta" in events
    assert "content_block_stop" in events
    assert "message_delta" in events
    assert events[-1] == "message_stop"
    delta = next(f for f in frames if f.event == "content_block_delta")
    assert _decode(delta)["delta"] == {"type": "text_delta", "text": "hi"}
    start = next(f for f in frames if f.event == "content_block_start")
    assert _decode(start)["content_block"] == {"type": "text", "text": ""}
    assert _decode(start)["index"] == 0


def _verify_text_coalesces_on_single_block(frames: list[ServerSentEvent]) -> None:
    starts = [f for f in frames if f.event == "content_block_start"]
    assert len(starts) == 1
    deltas = [_decode(f)["delta"]["text"] for f in frames if f.event == "content_block_delta"]
    assert deltas == ["hi", " there"]


def _verify_thinking_routes_to_thinking_block(frames: list[ServerSentEvent]) -> None:
    starts = [_decode(f)["content_block"] for f in frames if f.event == "content_block_start"]
    assert any(block["type"] == "thinking" for block in starts)
    deltas = [
        _decode(f)["delta"]
        for f in frames
        if f.event == "content_block_delta" and _decode(f)["delta"].get("type") == "thinking_delta"
    ]
    assert deltas == [{"type": "thinking_delta", "thinking": "thinking aloud"}]


def _verify_thinking_then_text_alternates_blocks(frames: list[ServerSentEvent]) -> None:
    block_types_in_order = [_decode(f)["content_block"]["type"] for f in frames if f.event == "content_block_start"]
    assert block_types_in_order == ["thinking", "text"]
    indices = [_decode(f)["index"] for f in frames if f.event == "content_block_start"]
    assert indices == [0, 1]


def _verify_text_then_thinking_alternates_blocks(frames: list[ServerSentEvent]) -> None:
    block_types_in_order = [_decode(f)["content_block"]["type"] for f in frames if f.event == "content_block_start"]
    assert block_types_in_order == ["text", "thinking"]


def _verify_tool_block_emits_input_json_delta(frames: list[ServerSentEvent]) -> None:
    start = next(
        f for f in frames if f.event == "content_block_start" and _decode(f)["content_block"]["type"] == "tool_use"
    )
    body = _decode(start)
    assert body["content_block"] == {"type": "tool_use", "id": "c1", "name": "lookup", "input": {}}
    delta = next(
        f for f in frames if f.event == "content_block_delta" and _decode(f)["delta"]["type"] == "input_json_delta"
    )
    assert _decode(delta)["delta"]["partial_json"] == json.dumps({"q": "x"})


def _verify_tool_after_text_closes_text_block(frames: list[ServerSentEvent]) -> None:
    starts_and_stops = [
        (f.event, _decode(f).get("index", _decode(f).get("content_block", {}).get("type")))
        for f in frames
        if f.event in ("content_block_start", "content_block_stop")
    ]
    assert starts_and_stops == [
        ("content_block_start", 0),
        ("content_block_stop", 0),
        ("content_block_start", 1),
        ("content_block_stop", 1),
    ]


def _verify_empty_text_skipped(frames: list[ServerSentEvent]) -> None:
    starts = [f for f in frames if f.event == "content_block_start"]
    assert starts == []


def _verify_message_delta_carries_usage(frames: list[ServerSentEvent]) -> None:
    delta = next(f for f in frames if f.event == "message_delta")
    body = _decode(delta)
    assert body["usage"] == {"input_tokens": 7, "output_tokens": 3}


def _make_stop_reason_verifier(expected: str) -> t.Callable[[list[ServerSentEvent]], None]:
    def _verify(frames: list[ServerSentEvent]) -> None:
        delta = next(f for f in frames if f.event == "message_delta")
        assert _decode(delta)["delta"]["stop_reason"] == expected

    return _verify


def _verify_error_emits_error_event(frames: list[ServerSentEvent]) -> None:
    error = next(f for f in frames if f.event == "error")
    assert _decode(error)["error"] == {"type": "api_error", "message": "LLM stream generation failed"}
    delta = next(f for f in frames if f.event == "message_delta")
    assert _decode(delta)["delta"]["stop_reason"] == "end_turn"
    assert frames[-1].event == "message_stop"


def _verify_skip_drops_leading_frames(frames: list[ServerSentEvent]) -> None:
    assert frames[-1].event == "message_stop"
    assert all(f.event != "message_start" for f in frames)


class TestCaseAnthropicRenderer:
    """Cover :class:`AnthropicRenderer` end-to-end across the Messages API SSE FSM and the engine-driven
    :attr:`Renderer.skip` suppression hook.

    Each parametrized row exercises one wire-shape concern: per-stream identity (``msg_`` prefix anchored
    to a generation UUID), the content-block lifecycle (``content_block_start`` / ``_delta`` / ``_stop``),
    text vs. thinking block alternation, tool-use emission with ``input_json_delta`` payload, the terminal
    ``message_delta`` usage tally, the ``stop_reason`` mapping, the error envelope, and the engine's
    leading-frame suppression hook.
    """

    @pytest.mark.parametrize(
        ["driver", "verify"],
        [
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hi"),
                        StopEvent(stop_reason="stop"),
                    ],
                ),
                _verify_message_envelope_id_prefix,
                id="message_envelope_id_prefix",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hi"),
                        StopEvent(stop_reason="stop"),
                    ],
                ),
                _verify_text_block_lifecycle,
                id="text_block_lifecycle",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hi"),
                        TextEvent(channel="output", text=" there"),
                        StopEvent(stop_reason="stop"),
                    ],
                ),
                _verify_text_coalesces_on_single_block,
                id="text_coalesces_on_single_block",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="thinking", text="thinking aloud"),
                        StopEvent(stop_reason="stop"),
                    ],
                ),
                _verify_thinking_routes_to_thinking_block,
                id="thinking_routes_to_thinking_block",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="thinking", text="t"),
                        TextEvent(channel="output", text="o"),
                        StopEvent(stop_reason="stop"),
                    ],
                ),
                _verify_thinking_then_text_alternates_blocks,
                id="thinking_then_text_alternates_blocks",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="o"),
                        TextEvent(channel="thinking", text="t"),
                        StopEvent(stop_reason="stop"),
                    ],
                ),
                _verify_text_then_thinking_alternates_blocks,
                id="text_then_thinking_alternates_blocks",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        ToolEvent(id="c1", name="lookup", arguments={"q": "x"}),
                        StopEvent(stop_reason="tool_use"),
                    ],
                ),
                _verify_tool_block_emits_input_json_delta,
                id="tool_block_emits_input_json_delta",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="o"),
                        ToolEvent(id="c1", name="lookup", arguments={"q": "x"}),
                        StopEvent(stop_reason="tool_use"),
                    ],
                ),
                _verify_tool_after_text_closes_text_block,
                id="tool_after_text_closes_text_block",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text=""),
                        TextEvent(channel="thinking", text=""),
                        StopEvent(stop_reason="stop"),
                    ],
                ),
                _verify_empty_text_skipped,
                id="empty_text_does_not_open_block",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0, input_tokens=7),
                        TextEvent(channel="output", text="ok"),
                        StopEvent(stop_reason="stop", output_tokens=3),
                    ],
                ),
                _verify_message_delta_carries_usage,
                id="message_delta_carries_usage",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="stop")]),
                _make_stop_reason_verifier("end_turn"),
                id="stop_reason_stop",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="max_tokens")]),
                _make_stop_reason_verifier("max_tokens"),
                id="stop_reason_max_tokens",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="tool_use")]),
                _make_stop_reason_verifier("tool_use"),
                id="stop_reason_tool_use",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="content_filter")]),
                _make_stop_reason_verifier("end_turn"),
                id="stop_reason_content_filter",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="cancelled")]),
                _make_stop_reason_verifier("end_turn"),
                id="stop_reason_cancelled",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="unknown")]),
                _make_stop_reason_verifier("end_turn"),
                id="stop_reason_unknown",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason=None)]),
                _make_stop_reason_verifier("end_turn"),
                id="stop_reason_none",
            ),
            pytest.param(
                _build_driver([StopEvent(stop_reason="error")]),
                _verify_error_emits_error_event,
                id="error_emits_error_event",
            ),
            pytest.param(
                _build_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hi"),
                        StopEvent(stop_reason="stop"),
                    ],
                    skip=2,
                ),
                _verify_skip_drops_leading_frames,
                id="skip_drops_leading_frames",
            ),
        ],
    )
    async def test_render(
        self,
        driver: _Driver,
        verify: t.Callable[[list[ServerSentEvent]], None],
    ) -> None:
        verify(await driver())

    def test_no_generation_id_falls_back_to_random(self) -> None:
        renderer = AnthropicRenderer(model="m")
        assert renderer._id.startswith("msg_")
