import logging
import pathlib
import typing as t

import pytest

from flama.exceptions import FrameworkNotInstalled
from flama.models.streams import FileStreamsBackend, StreamsRegistry
from flama.models.transport.output.llm.buffer import EventBuffer
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent
from flama.models.wire.dialect.base import CoalescingRenderer, Renderer


@pytest.fixture(scope="function")
async def backend(tmp_path: pathlib.Path) -> t.AsyncIterator[FileStreamsBackend]:
    backend = FileStreamsBackend(path=tmp_path, remove=False)
    await backend.aopen()
    try:
        yield backend
    finally:
        await backend.aclose()


@pytest.fixture(scope="function")
def registry(backend: FileStreamsBackend) -> StreamsRegistry:
    return StreamsRegistry(backend=backend)


class _RecordingRenderer(Renderer[Event]):
    """Test helper. Forwards every block verbatim and records the dispatch sequence."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def on_start(self, block: StartEvent) -> t.Iterable[Event]:
        self.calls.append("start")
        yield block

    def on_text(self, block: TextEvent) -> t.Iterable[Event]:
        self.calls.append("text")
        yield block

    def on_tool(self, block: ToolEvent) -> t.Iterable[Event]:
        self.calls.append("tool")
        yield block

    def on_trace(self, block: TraceEvent) -> t.Iterable[Event]:
        self.calls.append("trace")
        return ()

    def on_stop(self, block: StopEvent) -> t.Iterable[Event]:
        self.calls.append("stop")
        yield block

    def flush(self) -> t.Iterable[Event]:
        self.calls.append("flush")
        return ()


class TestCaseRenderer:
    """Cover the Renderer ABC contract."""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            Renderer()  # type: ignore[abstract]

    def test_default_no_op_methods(self) -> None:
        class _Minimal(Renderer[Event]):
            def on_text(self, block: TextEvent) -> t.Iterable[Event]:
                return ()

            def on_tool(self, block: ToolEvent) -> t.Iterable[Event]:
                return ()

            def on_stop(self, block: StopEvent) -> t.Iterable[Event]:
                return ()

        renderer = _Minimal()

        assert list(renderer.on_start(StartEvent(id="m", created=0))) == []
        assert list(renderer.on_trace(TraceEvent(token_count=1))) == []
        assert list(renderer.flush()) == []


class TestCaseCoalescingRenderer:
    """Cover the L2-to-L2 default strategy via :class:`EventBuffer` integration."""

    @pytest.mark.parametrize(
        ["source", "expected"],
        [
            pytest.param(
                [
                    TextEvent(channel="output", text="he"),
                    TextEvent(channel="output", text="llo"),
                ],
                [TextEvent(channel="output", text="hello")],
                id="same_channel_merged",
            ),
            pytest.param(
                [
                    TextEvent(channel="thinking", text="..."),
                    TextEvent(channel="output", text="hi"),
                    TextEvent(channel="output", text="!"),
                ],
                [
                    TextEvent(channel="thinking", text="..."),
                    TextEvent(channel="output", text="hi!"),
                ],
                id="channel_transition_emits_separate_blocks",
            ),
            pytest.param(
                [
                    TextEvent(channel="output", text="hi"),
                    ToolEvent(id="c1", name="f", arguments={"a": 1}),
                    TextEvent(channel="output", text="bye"),
                ],
                [
                    TextEvent(channel="output", text="hi"),
                    ToolEvent(id="c1", name="f", arguments={"a": 1}),
                    TextEvent(channel="output", text="bye"),
                ],
                id="tool_blocks_pass_through",
            ),
            pytest.param(
                [
                    TextEvent(channel="output", text="hi"),
                    TraceEvent(token_count=3),
                    TextEvent(channel="output", text="!"),
                ],
                [TextEvent(channel="output", text="hi!")],
                id="traces_are_dropped",
            ),
            pytest.param(
                [
                    StartEvent(id="m", created=0),
                    TextEvent(channel="output", text="x"),
                    StopEvent(stop_reason="stop"),
                ],
                [TextEvent(channel="output", text="x")],
                id="lifecycle_markers_dropped",
            ),
        ],
    )
    async def test_assemble(self, source: list[Event], expected: list[Event]) -> None:
        buffer = EventBuffer(source, CoalescingRenderer())

        assert [block async for block in buffer] == expected

    async def test_flush_drains_on_exhaustion_without_stop_event(self) -> None:
        buffer = EventBuffer(
            [
                TextEvent(channel="output", text="a"),
                TextEvent(channel="output", text="b"),
            ],
            CoalescingRenderer(),
        )

        assert [block async for block in buffer] == [TextEvent(channel="output", text="ab")]


class TestCaseEventBuffer:
    """Cover the FSM engine: lifecycle, skip, dispatch, assemble, error pump."""

    async def test_init_empty_source(self) -> None:
        buffer = EventBuffer([], CoalescingRenderer())

        assert [block async for block in buffer] == []
        with pytest.raises(RuntimeError, match="must be consumed"):
            _ = buffer.start
        with pytest.raises(RuntimeError, match="must be consumed"):
            _ = buffer.stop

    async def test_lifecycle_exposed_via_properties(self) -> None:
        start = StartEvent(id="abc", created=7, input_tokens=4)
        stop = StopEvent(stop_reason="stop", output_tokens=1)
        buffer = EventBuffer([start, TextEvent(channel="output", text="hi"), stop], CoalescingRenderer())

        assert [block async for block in buffer] == [TextEvent(channel="output", text="hi")]
        assert buffer.start == start
        assert buffer.stop == stop

    async def test_renderer_skip_drops_leading_outputs(self) -> None:
        renderer = CoalescingRenderer()
        renderer.skip = 1
        buffer = EventBuffer(
            [
                StartEvent(id="m", created=0),
                TextEvent(channel="output", text="hi"),
                ToolEvent(id="c1", name="f", arguments={}),
                StopEvent(stop_reason="stop"),
            ],
            renderer,
        )

        assert [block async for block in buffer] == [ToolEvent(id="c1", name="f", arguments={})]

    async def test_assemble_returns_tuple(self) -> None:
        buffer = EventBuffer(
            [
                StartEvent(id="m", created=0),
                TextEvent(channel="output", text="hi"),
                StopEvent(stop_reason="stop"),
            ],
            CoalescingRenderer(),
        )

        events = await buffer.assemble()

        assert events == (TextEvent(channel="output", text="hi"),)
        assert isinstance(events, tuple)

    async def test_dispatch_routes_each_kind_and_calls_flush_before_stop(self) -> None:
        renderer = _RecordingRenderer()
        buffer = EventBuffer(
            [
                StartEvent(id="m", created=0),
                TextEvent(channel="output", text="hi"),
                ToolEvent(id="c1", name="f", arguments={}),
                TraceEvent(token_count=1),
                StopEvent(stop_reason="stop"),
            ],
            renderer,
        )

        _ = [block async for block in buffer]

        assert renderer.calls == ["start", "text", "tool", "trace", "flush", "stop", "flush"]

    async def test_flush_called_on_source_exhaustion_without_stop(self) -> None:
        renderer = _RecordingRenderer()
        buffer = EventBuffer([TextEvent(channel="output", text="hi")], renderer)

        _ = [block async for block in buffer]

        assert renderer.calls == ["text", "flush"]

    async def test_replay_from_stream_buffer(self, registry: StreamsRegistry) -> None:
        _, source_buffer = await registry.add("m").create()
        await source_buffer.append(StartEvent(id=str(source_buffer.id), created=0))
        await source_buffer.append(TextEvent(channel="output", text="a"))
        await source_buffer.append(TextEvent(channel="output", text="b"))
        await source_buffer.append(StopEvent(stop_reason="stop"))

        buffer = EventBuffer(source_buffer, CoalescingRenderer())

        assert [block async for block in buffer] == [TextEvent(channel="output", text="ab")]
        assert buffer.start.id == str(source_buffer.id)
        assert buffer.stop.stop_reason == "stop"

    @pytest.mark.parametrize(
        ["error", "expected_log_substring"],
        [
            pytest.param(FrameworkNotInstalled("torch"), "missing dependency", id="framework_not_installed"),
            pytest.param(RuntimeError("boom"), "generation failed", id="generic_exception"),
        ],
    )
    async def test_error_synthesises_stop_block(
        self,
        error: Exception,
        expected_log_substring: str,
        caplog_flama: pytest.LogCaptureFixture,
    ) -> None:
        """Cover the exception-handling pump in :meth:`EventBuffer.__anext__`: the engine synthesises
        a terminal :class:`StopEvent` with ``stop_reason='error'`` on any source exception, marks
        itself exhausted, and terminates cleanly so concrete handlers don't need their own
        failure-path code.

        Uses :fixture:`caplog_flama` rather than the stock ``caplog``: the runtime ``dictConfig``
        sets ``propagate=False`` on the ``flama`` logger, so a root-bound capture handler would miss
        these records whenever another test in the same xdist worker has applied that config first.
        """
        start = StartEvent(id="abc", created=0)

        async def _source() -> t.AsyncIterator[Event]:
            yield start
            yield TextEvent(channel="output", text="hi")
            raise error

        buffer = EventBuffer(_source(), CoalescingRenderer())

        with caplog_flama.at_level(logging.ERROR, logger="flama.models.transport.output.llm.buffer"):
            collected = [block async for block in buffer]

        assert collected == [TextEvent(channel="output", text="hi")]
        assert buffer.start == start
        assert buffer.stop.stop_reason == "error"
        assert any(expected_log_substring in record.getMessage().lower() for record in caplog_flama.records)

    async def test_terminates_after_synthesised_stop(self) -> None:
        async def _source() -> t.AsyncIterator[Event]:
            yield TextEvent(channel="output", text="a")
            raise RuntimeError("boom")

        buffer = EventBuffer(_source(), CoalescingRenderer())

        _ = [block async for block in buffer]

        with pytest.raises(StopAsyncIteration):
            await buffer.__anext__()
