import asyncio
import json
import pathlib
import typing as t
import uuid

import pytest

from flama.http.responses.sse import ServerSentEvent
from flama.models.streams import FileStreamsBackend, StreamBuffer, StreamsRegistry
from flama.models.transport.output.llm.buffer import EventBuffer
from flama.models.transport.output.llm.event import Event as TransportEvent
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent
from flama.models.wire.dialect.llm.native.renderer import EventsRenderer


@pytest.fixture(scope="function")
async def stream_backend(tmp_path: pathlib.Path) -> t.AsyncIterator[FileStreamsBackend]:
    backend = FileStreamsBackend(path=tmp_path, remove=False)
    await backend.aopen()
    try:
        yield backend
    finally:
        await backend.aclose()


@pytest.fixture(scope="function")
def registry(stream_backend: FileStreamsBackend) -> StreamsRegistry:
    return StreamsRegistry(backend=stream_backend)


_SAMPLE_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_OTHER_UUID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _decode(frame: ServerSentEvent) -> dict[str, t.Any]:
    return json.loads(frame.data)


_Driver = t.Callable[[StreamsRegistry], t.Awaitable[list[ServerSentEvent]]]


def _list_driver(events: list[TransportEvent], **kwargs: t.Any) -> _Driver:
    async def _driver(_: StreamsRegistry) -> list[ServerSentEvent]:
        renderer = EventsRenderer(message_id=_SAMPLE_UUID, **kwargs)
        return [frame async for frame in EventBuffer(events, renderer)]

    return _driver


def _completed_buffer_driver() -> _Driver:
    async def _driver(registry: StreamsRegistry) -> list[ServerSentEvent]:
        _, buffer = await registry.add("m").create()
        await buffer.append(StartEvent(id=str(buffer.id), created=0))
        await buffer.append(TextEvent(channel="output", text="x"))
        await buffer.append(StopEvent(stop_reason="stop"))
        renderer = EventsRenderer(message_id=buffer.id, retry=5000)
        return [frame async for frame in EventBuffer(buffer, renderer)]

    return _driver


def _tailing_buffer_driver() -> _Driver:
    async def _driver(registry: StreamsRegistry) -> list[ServerSentEvent]:
        _, buffer = await registry.add("m").create()
        await buffer.append(StartEvent(id=str(buffer.id), created=0))

        async def _produce(buf: StreamBuffer) -> None:
            await asyncio.sleep(0.01)
            await buf.append(TextEvent(channel="output", text="late"))
            await buf.append(StopEvent(stop_reason="stop"))

        producer = asyncio.create_task(_produce(buffer))
        try:
            renderer = EventsRenderer(message_id=buffer.id)
            return [frame async for frame in EventBuffer(buffer, renderer)]
        finally:
            await producer

    return _driver


def _verify_message_start_carries_id_and_created(frames: list[ServerSentEvent]) -> None:
    assert len(frames) == 1
    assert frames[0].event == "message.start"
    assert frames[0].id == f"{_SAMPLE_UUID}.1"
    assert _decode(frames[0]) == {"type": "message.start", "id": "abc", "created": 42}


def _verify_message_start_carries_retry(frames: list[ServerSentEvent]) -> None:
    assert frames[0].retry == 5000


def _verify_text_emission(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == ["block.start", "block.delta", "block.stop"]
    assert _decode(frames[0]) == {
        "type": "block.start",
        "index": 0,
        "block": {"type": "text", "channel": "output"},
    }
    assert _decode(frames[1]) == {
        "type": "block.delta",
        "index": 0,
        "delta": {"type": "text.delta", "text": "hi"},
    }
    assert _decode(frames[2]) == {"type": "block.stop", "index": 0}


def _verify_empty_text_skips_delta(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == ["block.start", "block.stop"]


def _verify_same_channel_only_emits_delta(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == ["block.start", "block.delta", "block.delta", "block.stop"]


def _verify_channel_transition(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == [
        "block.start",
        "block.delta",
        "block.stop",
        "block.start",
        "block.delta",
        "block.stop",
    ]
    assert _decode(frames[0])["index"] == 0
    assert _decode(frames[3])["index"] == 1


def _verify_consecutive_tools(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == [
        "block.start",
        "block.delta",
        "block.stop",
        "block.start",
        "block.delta",
        "block.stop",
    ]


def _verify_tool_descriptor(frames: list[ServerSentEvent]) -> None:
    assert _decode(frames[0]) == {
        "type": "block.start",
        "index": 0,
        "block": {"type": "tool", "id": "c1", "name": "f", "arguments": {}},
    }
    assert _decode(frames[1]) == {
        "type": "block.delta",
        "index": 0,
        "delta": {"type": "tool.delta", "name": "f", "arguments": {"a": 1}},
    }


def _verify_text_to_tool_transition(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == [
        "block.start",
        "block.delta",
        "block.stop",
        "block.start",
        "block.delta",
        "block.stop",
    ]


def _verify_stop_block_emits_message_stop(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == ["block.start", "block.delta", "block.stop", "message.stop"]
    assert _decode(frames[3]) == {"type": "message.stop", "stop_reason": "stop"}


def _verify_message_stop_includes_output_tokens(frames: list[ServerSentEvent]) -> None:
    assert _decode(frames[0]) == {"type": "message.stop", "stop_reason": "stop", "output_tokens": 2}


def _verify_message_stop_minimal(frames: list[ServerSentEvent]) -> None:
    assert _decode(frames[0]) == {"type": "message.stop"}


def _verify_stop_block_with_error(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == ["error", "message.stop"]
    assert _decode(frames[0]) == {
        "type": "error",
        "status": 500,
        "detail": "LLM stream generation failed",
    }


def _verify_trace_below_threshold_emits_nothing(frames: list[ServerSentEvent]) -> None:
    assert frames == []


def _verify_trace_above_threshold_emits_message_delta(frames: list[ServerSentEvent]) -> None:
    deltas = [f for f in frames if f.event == "message.delta"]
    assert len(deltas) == 1
    assert _decode(deltas[0]) == {"type": "message.delta", "output_tokens": 64}


def _verify_sequence_ids_monotonic(frames: list[ServerSentEvent]) -> None:
    assert [f.id for f in frames] == [
        f"{_SAMPLE_UUID}.1",
        f"{_SAMPLE_UUID}.2",
        f"{_SAMPLE_UUID}.3",
        f"{_SAMPLE_UUID}.4",
        f"{_SAMPLE_UUID}.5",
    ]


def _verify_resume_id_skips_already_delivered(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == ["block.delta", "block.stop", "message.stop"]
    assert [f.id for f in frames] == [
        f"{_SAMPLE_UUID}.3",
        f"{_SAMPLE_UUID}.4",
        f"{_SAMPLE_UUID}.5",
    ]


def _verify_stream_replay_replays_completed_buffer(frames: list[ServerSentEvent]) -> None:
    assert [f.event for f in frames] == [
        "message.start",
        "block.start",
        "block.delta",
        "block.stop",
        "message.stop",
    ]
    assert frames[0].retry == 5000


def _verify_stream_replay_tails_until_stop(frames: list[ServerSentEvent]) -> None:
    events = [f.event for f in frames]
    assert "message.start" in events
    assert "message.stop" in events
    deltas = [f for f in frames if f.event == "block.delta"]
    assert deltas and _decode(deltas[0])["delta"]["text"] == "late"


class TestCaseEventsRenderer:
    """Cover :class:`EventsRenderer` end-to-end: the :meth:`_parse_event_id` resume-id decoder, the
    constructor's skip / sequence wiring, the streaming wire shape emitted to clients, the monotonic
    ID sequencing across resumed connections, and the stream-replay path through
    :class:`EventBuffer`.
    """

    @pytest.mark.parametrize(
        ["value", "message_id", "expected"],
        [
            pytest.param(f"{_SAMPLE_UUID}.5", _SAMPLE_UUID, 5, id="matching_message_id_returns_sequence"),
            pytest.param(f"{_OTHER_UUID}.5", _SAMPLE_UUID, None, id="mismatched_message_id_returns_none"),
            pytest.param(None, _SAMPLE_UUID, None, id="none"),
            pytest.param("", _SAMPLE_UUID, None, id="empty"),
            pytest.param("bogus", _SAMPLE_UUID, None, id="malformed"),
            pytest.param("not-a-uuid.5", _SAMPLE_UUID, None, id="not_a_uuid"),
            pytest.param(f"{_SAMPLE_UUID}.bogus", _SAMPLE_UUID, None, id="non_numeric_sequence"),
        ],
    )
    def test_parse_event_id(self, value: str | None, message_id: uuid.UUID, expected: int | None) -> None:
        assert EventsRenderer._parse_event_id(value, message_id=message_id) == expected

    @pytest.mark.parametrize(
        ["resume_id", "expected_skip"],
        [
            pytest.param(None, 0, id="fresh_state"),
            pytest.param(f"{_SAMPLE_UUID}.5", 5, id="resume_id_matching_message_id_seeds_skip"),
            pytest.param(f"{_OTHER_UUID}.5", 0, id="resume_id_mismatched_message_id_falls_back"),
            pytest.param("bogus", 0, id="resume_id_malformed_falls_back"),
        ],
    )
    def test_init(self, resume_id: str | None, expected_skip: int) -> None:
        renderer = EventsRenderer(message_id=_SAMPLE_UUID, resume_id=resume_id)

        assert renderer.skip == expected_skip

    @pytest.mark.parametrize(
        ["driver", "verify"],
        [
            pytest.param(
                _list_driver([StartEvent(id="abc", created=42)]),
                _verify_message_start_carries_id_and_created,
                id="message_start_carries_id_and_created",
            ),
            pytest.param(
                _list_driver([StartEvent(id="abc", created=0)], retry=5000),
                _verify_message_start_carries_retry,
                id="message_start_carries_retry",
            ),
            pytest.param(
                _list_driver([TextEvent(channel="output", text="hi")]),
                _verify_text_emission,
                id="text_emission_emits_block_start_and_delta",
            ),
            pytest.param(
                _list_driver([TextEvent(channel="output", text="")]),
                _verify_empty_text_skips_delta,
                id="empty_text_skips_delta",
            ),
            pytest.param(
                _list_driver(
                    [
                        TextEvent(channel="output", text="hi"),
                        TextEvent(channel="output", text=" there"),
                    ]
                ),
                _verify_same_channel_only_emits_delta,
                id="same_channel_only_emits_delta",
            ),
            pytest.param(
                _list_driver(
                    [
                        TextEvent(channel="thinking", text="..."),
                        TextEvent(channel="output", text="ans"),
                    ]
                ),
                _verify_channel_transition,
                id="channel_transition_closes_previous_block",
            ),
            pytest.param(
                _list_driver(
                    [
                        ToolEvent(id="c1", name="f", arguments={"a": 1}),
                        ToolEvent(id="c2", name="g", arguments={}),
                    ]
                ),
                _verify_consecutive_tools,
                id="consecutive_tools_open_and_close",
            ),
            pytest.param(
                _list_driver([ToolEvent(id="c1", name="f", arguments={"a": 1})]),
                _verify_tool_descriptor,
                id="tool_start_carries_descriptor_with_empty_arguments",
            ),
            pytest.param(
                _list_driver(
                    [
                        TextEvent(channel="output", text="thinking"),
                        ToolEvent(id="c1", name="f", arguments={}),
                    ]
                ),
                _verify_text_to_tool_transition,
                id="text_to_tool_transition_closes_text",
            ),
            pytest.param(
                _list_driver([TextEvent(channel="output", text="hi"), StopEvent(stop_reason="stop")]),
                _verify_stop_block_emits_message_stop,
                id="stop_block_closes_open_block_and_emits_message_stop",
            ),
            pytest.param(
                _list_driver([StopEvent(stop_reason="stop", output_tokens=2)]),
                _verify_message_stop_includes_output_tokens,
                id="message_stop_includes_output_tokens",
            ),
            pytest.param(
                _list_driver([StopEvent()]),
                _verify_message_stop_minimal,
                id="message_stop_minimal_when_no_fields",
            ),
            pytest.param(
                _list_driver([StopEvent(stop_reason="error")]),
                _verify_stop_block_with_error,
                id="stop_block_with_error_injects_error_frame",
            ),
            pytest.param(
                _list_driver([TraceEvent(token_count=4)]),
                _verify_trace_below_threshold_emits_nothing,
                id="trace_below_flush_threshold_emits_nothing",
            ),
            pytest.param(
                _list_driver(
                    [
                        StartEvent(id="m", created=0, input_tokens=10),
                        TraceEvent(token_count=64, finish_reason="stop"),
                    ]
                ),
                _verify_trace_above_threshold_emits_message_delta,
                id="trace_above_flush_threshold_emits_message_delta",
            ),
            pytest.param(
                _list_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hi"),
                        StopEvent(stop_reason="stop"),
                    ]
                ),
                _verify_sequence_ids_monotonic,
                id="sequence_ids_are_monotonic",
            ),
            pytest.param(
                _list_driver(
                    [
                        StartEvent(id="m", created=0),
                        TextEvent(channel="output", text="hi"),
                        StopEvent(stop_reason="stop"),
                    ],
                    resume_id=f"{_SAMPLE_UUID}.2",
                ),
                _verify_resume_id_skips_already_delivered,
                id="sequence_resume_id_skips_already_delivered_frames",
            ),
            pytest.param(
                _completed_buffer_driver(),
                _verify_stream_replay_replays_completed_buffer,
                id="stream_replay_replays_completed_buffer",
            ),
            pytest.param(
                _tailing_buffer_driver(),
                _verify_stream_replay_tails_until_stop,
                id="stream_replay_tails_until_stop",
            ),
        ],
    )
    async def test_render(
        self,
        registry: StreamsRegistry,
        driver: _Driver,
        verify: t.Callable[[list[ServerSentEvent]], None],
    ) -> None:
        frames = await driver(registry)

        verify(frames)
