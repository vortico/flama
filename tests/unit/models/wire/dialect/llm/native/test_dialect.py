import asyncio
import json
import pathlib
import typing as t
import uuid

import pytest

from flama.http.responses.sse import ServerSentEvent
from flama.models.streams import (
    DEFAULT_EPHEMERAL_CAPACITY,
    FileStreamsBackend,
    InMemoryStreamsBackend,
    StreamBuffer,
)
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent
from flama.models.wire.dialect.llm.native import NativeAssembler, NativeDialect, NativeParser
from flama.models.wire.dialect.llm.native.renderer import EventsRenderer

_BUFFER_UUID = uuid.UUID("00000000-0000-0000-0000-000000000abc")
_OTHER_UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture(scope="function")
async def stream_backend(tmp_path: pathlib.Path) -> t.AsyncIterator[FileStreamsBackend]:
    backend = FileStreamsBackend(path=tmp_path, remove=False)
    await backend.aopen()
    try:
        yield backend
    finally:
        await backend.aclose()


@pytest.fixture(scope="function")
async def stream_buffer(stream_backend: FileStreamsBackend) -> t.AsyncIterator[StreamBuffer]:
    ephemeral = InMemoryStreamsBackend(capacity=DEFAULT_EPHEMERAL_CAPACITY)
    await ephemeral.aopen()
    try:
        yield StreamBuffer(model="m", id=_BUFFER_UUID, ephemeral=ephemeral, backend=stream_backend)
    finally:
        await ephemeral.aclose()


def _events() -> list:
    return [
        StartEvent(id="msg-1", created=1234567890, input_tokens=5),
        TextEvent(channel="output", text="Hello"),
        StopEvent(stop_reason="stop", output_tokens=2),
    ]


async def _drive(buffer: StreamBuffer, events: list, **kwargs: t.Any) -> list[ServerSentEvent]:
    async def _producer() -> t.AsyncIterator:
        for event in events:
            yield event

    drain_task = asyncio.create_task(buffer.load(_producer()))
    try:
        return [frame async for frame in NativeDialect.render(buffer, message_id=buffer.id, retry=5000, **kwargs)]
    finally:
        await drain_task


class TestCaseNativeDialect:
    """Cover :class:`NativeDialect` end-to-end: strategy bindings, the :meth:`render` façade
    composition (engine + ``EventsRenderer``) including resume-id semantics and SSE retry, plus
    the stream-only :meth:`assemble` contract.
    """

    @pytest.mark.parametrize(
        ["attr", "expected"],
        [
            pytest.param("PARSER", NativeParser, id="parser"),
            pytest.param("RENDERER", EventsRenderer, id="renderer"),
            pytest.param("ASSEMBLER", NativeAssembler, id="assembler"),
        ],
    )
    def test_bindings(self, attr: str, expected: type) -> None:
        assert getattr(NativeDialect, attr) is expected

    @pytest.mark.parametrize(
        ["resume_id", "expected_first_suffix", "expected_count_delta"],
        [
            pytest.param(None, ".1", 0, id="baseline"),
            pytest.param(f"{_BUFFER_UUID}.2", ".3", -2, id="resume_id_match_drops_delivered"),
            pytest.param(f"{_OTHER_UUID}.10", ".1", 0, id="resume_id_mismatched_message_id_falls_back"),
            pytest.param("not-an-id", ".1", 0, id="resume_id_malformed_falls_back"),
        ],
    )
    async def test_render(
        self,
        stream_buffer: StreamBuffer,
        resume_id: str | None,
        expected_first_suffix: str,
        expected_count_delta: int,
    ) -> None:
        baseline = await _drive(stream_buffer, _events())

        kwargs: dict[str, t.Any] = {}
        if resume_id is not None:
            kwargs["resume_id"] = resume_id
        frames = await _drive(stream_buffer, _events(), **kwargs)

        assert all(isinstance(frame, ServerSentEvent) for frame in frames)
        assert len(frames) == len(baseline) + expected_count_delta
        assert frames[0].id is not None
        assert frames[0].id.endswith(expected_first_suffix)

        if expected_count_delta == 0:
            event_names = [frame.event for frame in frames]
            assert event_names[0] == "message.start"
            assert event_names[-1] == "message.stop"
            assert "block.start" in event_names
            assert "block.delta" in event_names
            assert "block.stop" in event_names

            message_start = next(frame for frame in frames if frame.event == "message.start")
            assert json.loads(message_start.data)["type"] == "message.start"
            assert message_start.retry == 5000
        else:
            assert frames[0].id == baseline[-expected_count_delta].id

    async def test_assemble(self) -> None:
        with pytest.raises(NotImplementedError, match="stream-only"):
            await NativeDialect.assemble(_events())
