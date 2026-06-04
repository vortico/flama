import asyncio
import pathlib
import time
import typing as t
import uuid
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from flama.exceptions import FrameworkNotInstalled
from flama.models.streams import (
    CleanupTask,
    FileStreamsBackend,
    InMemoryStreamsBackend,
    ModelStreams,
    StreamBuffer,
    StreamsBackend,
    StreamsRegistry,
)
from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent


@pytest.fixture(scope="function")
async def backend(tmp_path: pathlib.Path) -> t.AsyncIterator[FileStreamsBackend]:
    """Provide an opened :class:`FileStreamsBackend` pinned to a per-test ``tmp_path`` and close it afterwards."""
    backend = FileStreamsBackend(path=tmp_path, remove=False)
    await backend.aopen()
    try:
        yield backend
    finally:
        await backend.aclose()


@pytest.fixture(scope="function")
async def ephemeral_backend() -> t.AsyncIterator[InMemoryStreamsBackend]:
    """Provide an opened :class:`InMemoryStreamsBackend` and close it afterwards."""
    backend = InMemoryStreamsBackend()
    await backend.aopen()
    try:
        yield backend
    finally:
        await backend.aclose()


class TestCaseStreamsBackend:
    """Cover the abstract contract surfaces of :class:`StreamsBackend`."""

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(TypeError, id="abstract")],
        indirect=["exception"],
    )
    def test_init(self, exception) -> None:
        with exception:
            StreamsBackend()  # ty: ignore[call-non-callable]


class TestCaseFileStreamsBackend:
    """Cover :class:`FileStreamsBackend` lifecycle, JSONL round-trip, and slicing semantics."""

    @pytest.mark.parametrize(
        ["pinned", "remove", "expected_kept"],
        [
            pytest.param(False, True, False, id="owned_tempdir_cleaned"),
            pytest.param(True, True, False, id="pinned_path_cleaned"),
            pytest.param(True, False, True, id="pinned_path_kept"),
        ],
    )
    async def test_aopen_aclose_lifecycle(
        self,
        tmp_path: pathlib.Path,
        pinned: bool,
        remove: bool,
        expected_kept: bool,
    ) -> None:
        target = (tmp_path / "pinned") if pinned else None
        backend = FileStreamsBackend(path=target, remove=remove)

        await backend.aopen()
        root = backend.root

        assert root.exists()
        assert root.is_dir()
        if pinned:
            assert root == target

        await backend.aclose()

        assert root.exists() is expected_kept

    @pytest.mark.parametrize(
        ["calls"],
        [pytest.param(1, id="once"), pytest.param(2, id="twice"), pytest.param(3, id="thrice")],
    )
    async def test_aopen_aclose_idempotency(self, tmp_path: pathlib.Path, calls: int) -> None:
        backend = FileStreamsBackend(path=tmp_path, remove=False)

        for _ in range(calls):
            await backend.aopen()

        assert backend.root == tmp_path

        for _ in range(calls):
            await backend.aclose()

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param((RuntimeError, "not open"), id="not_open")],
        indirect=["exception"],
    )
    def test_root_requires_open(self, exception) -> None:
        backend = FileStreamsBackend()

        with exception:
            _ = backend.root

    @pytest.mark.parametrize(
        ["blocks"],
        [
            pytest.param([TextEvent(channel="output", text="hello")], id="text_only"),
            pytest.param(
                [
                    StartEvent(id="abc", created=42),
                    TextEvent(channel="output", text="hi"),
                    TraceEvent(token_count=3, finish_reason=None),
                    ToolEvent(id="call_x", name="search", arguments={"q": "weather"}),
                    StopEvent(stop_reason="stop", output_tokens=10),
                ],
                id="full_lifecycle",
            ),
        ],
    )
    async def test_append_and_read_round_trip(self, backend: FileStreamsBackend, blocks: list[Event]) -> None:
        key = uuid.uuid4()

        for block in blocks:
            await backend.append("m", key, block)

        assert await backend.read("m", key, 0, len(blocks)) == blocks

    async def test_append_writes_jsonl_under_model_subdir(self, backend: FileStreamsBackend) -> None:
        key = uuid.uuid4()

        await backend.append("a-model", key, TextEvent(channel="output", text="one"))

        path = backend.root / "a-model" / f"{key!s}.jsonl"
        assert path.exists()
        contents = path.read_text(encoding="utf-8").splitlines()
        assert len(contents) == 1
        assert '"kind":"text"' in contents[0]

    @pytest.mark.parametrize(
        ["total", "start", "end", "expected"],
        [
            pytest.param(5, 0, 5, [0, 1, 2, 3, 4], id="full_range"),
            pytest.param(5, 1, 4, [1, 2, 3], id="inner_slice"),
            pytest.param(5, 0, 1, [0], id="single_first"),
            pytest.param(5, 4, 5, [4], id="single_last"),
            pytest.param(5, 2, 2, [], id="empty_range"),
            pytest.param(5, 3, 10, [], id="end_past_length"),
            pytest.param(0, 0, 0, [], id="empty_store"),
        ],
    )
    async def test_read_slicing(
        self,
        backend: FileStreamsBackend,
        total: int,
        start: int,
        end: int,
        expected: list[int],
    ) -> None:
        key = uuid.uuid4()
        blocks = [TextEvent(channel="output", text=f"t{i}") for i in range(total)]
        for block in blocks:
            await backend.append("m", key, block)

        result = await backend.read("m", key, start, end)

        assert result == [blocks[i] for i in expected]

    async def test_pop_is_non_destructive(self, backend: FileStreamsBackend) -> None:
        """The on-disk log is the durable replay source; :meth:`pop` must not destroy lines."""
        key = uuid.uuid4()
        blocks = [TextEvent(channel="output", text=f"t{i}") for i in range(3)]
        for block in blocks:
            await backend.append("m", key, block)

        first = await backend.pop("m", key, 0, 3)
        second = await backend.pop("m", key, 0, 3)

        assert first == blocks
        assert second == blocks

    async def test_discard_removes_file_and_state(self, backend: FileStreamsBackend) -> None:
        key = uuid.uuid4()
        await backend.append("m", key, TextEvent(channel="output", text="x"))
        path = backend.root / "m" / f"{key!s}.jsonl"
        assert path.exists()

        await backend.discard("m", key)

        assert not path.exists()
        assert await backend.read("m", key, 0, 10) == []

    async def test_discard_unknown_is_noop(self, backend: FileStreamsBackend) -> None:
        await backend.discard("missing", uuid.uuid4())

    async def test_usage_reports_bytes_written(self, backend: FileStreamsBackend) -> None:
        key_a = uuid.uuid4()
        key_b = uuid.uuid4()
        await backend.append("m", key_a, TextEvent(channel="output", text="hello"))
        await backend.append("m", key_a, TextEvent(channel="output", text="world"))
        await backend.append("other", key_b, TextEvent(channel="output", text="x"))

        usage = backend.usage()

        path_a = backend.root / "m" / f"{key_a!s}.jsonl"
        path_b = backend.root / "other" / f"{key_b!s}.jsonl"
        assert usage[("m", key_a)] == path_a.stat().st_size
        assert usage[("other", key_b)] == path_b.stat().st_size
        assert usage[("m", key_a)] > usage[("other", key_b)]

    async def test_usage_empty_when_nothing_written(self, backend: FileStreamsBackend) -> None:
        assert backend.usage() == {}

    async def test_usage_drops_discarded_streams(self, backend: FileStreamsBackend) -> None:
        key = uuid.uuid4()
        await backend.append("m", key, TextEvent(channel="output", text="x"))
        assert ("m", key) in backend.usage()

        await backend.discard("m", key)

        assert ("m", key) not in backend.usage()


class TestCaseInMemoryStreamsBackend:
    """Cover :class:`InMemoryStreamsBackend` deque semantics: capacity, backpressure, and destructive pop."""

    @pytest.mark.parametrize(
        ["capacity", "exception"],
        [
            pytest.param(None, None, id="unbounded"),
            pytest.param(1, None, id="positive_capacity"),
            pytest.param(64, None, id="default_size"),
            pytest.param(0, (ValueError, "positive"), id="zero_rejected"),
            pytest.param(-1, (ValueError, "positive"), id="negative_rejected"),
        ],
        indirect=["exception"],
    )
    def test_init(self, capacity: int | None, exception) -> None:
        with exception:
            backend = InMemoryStreamsBackend(capacity=capacity)
            assert backend.capacity == capacity

    @pytest.mark.parametrize(
        ["blocks"],
        [
            pytest.param([TextEvent(channel="output", text="hello")], id="text_only"),
            pytest.param(
                [
                    StartEvent(id="abc", created=42),
                    TextEvent(channel="output", text="hi"),
                    TraceEvent(token_count=3, finish_reason=None),
                    ToolEvent(id="call_x", name="search", arguments={"q": "weather"}),
                    StopEvent(stop_reason="stop", output_tokens=10),
                ],
                id="full_lifecycle",
            ),
        ],
    )
    async def test_append_and_read_round_trip(
        self, ephemeral_backend: InMemoryStreamsBackend, blocks: list[Event]
    ) -> None:
        key = uuid.uuid4()

        for block in blocks:
            await ephemeral_backend.append("m", key, block)

        assert await ephemeral_backend.read("m", key, 0, len(blocks)) == blocks

    @pytest.mark.parametrize(
        ["total", "start", "end", "expected"],
        [
            pytest.param(5, 0, 5, [0, 1, 2, 3, 4], id="full_range"),
            pytest.param(5, 1, 4, [1, 2, 3], id="inner_slice"),
            pytest.param(5, 0, 1, [0], id="single_first"),
            pytest.param(5, 2, 2, [], id="empty_range"),
            pytest.param(5, 3, 10, [3, 4], id="end_past_length_returns_resident"),
            pytest.param(5, 10, 15, [], id="start_past_resident_returns_empty"),
            pytest.param(0, 0, 0, [], id="empty_store"),
        ],
    )
    async def test_read_slicing(
        self,
        ephemeral_backend: InMemoryStreamsBackend,
        total: int,
        start: int,
        end: int,
        expected: list[int],
    ) -> None:
        """In-memory ``read`` returns the intersection of the requested range with the *resident* deque.

        Differs from :class:`FileStreamsBackend.read` (which returns ``[]`` for any ``end`` past the line
        count) because the deque is a producer-consumer channel: producers and consumers don't share a
        single source of truth on length, and the consumer must see whatever has been written so far.
        """
        key = uuid.uuid4()
        blocks = [TextEvent(channel="output", text=f"t{i}") for i in range(total)]
        for block in blocks:
            await ephemeral_backend.append("m", key, block)

        result = await ephemeral_backend.read("m", key, start, end)

        assert result == [blocks[i] for i in expected]

    async def test_read_is_non_destructive(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        key = uuid.uuid4()
        for i in range(3):
            await ephemeral_backend.append("m", key, TextEvent(channel="output", text=f"t{i}"))

        assert await ephemeral_backend.read("m", key, 0, 3) == await ephemeral_backend.read("m", key, 0, 3)

    async def test_pop_drops_contiguous_head(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        """:meth:`pop` evicts only the requested head prefix; subsequent indices stay aligned."""
        key = uuid.uuid4()
        blocks = [TextEvent(channel="output", text=f"t{i}") for i in range(4)]
        for block in blocks:
            await ephemeral_backend.append("m", key, block)

        head = await ephemeral_backend.pop("m", key, 0, 2)
        rest = await ephemeral_backend.read("m", key, 2, 4)

        assert head == blocks[:2]
        assert rest == blocks[2:]
        assert ephemeral_backend.length()[("m", key)] == 4

    async def test_pop_leaves_head_intact_when_range_does_not_start_at_head(
        self, ephemeral_backend: InMemoryStreamsBackend
    ) -> None:
        """Popping a non-head range returns resident blocks without evicting anything."""
        key = uuid.uuid4()
        blocks = [TextEvent(channel="output", text=f"t{i}") for i in range(4)]
        for block in blocks:
            await ephemeral_backend.append("m", key, block)

        result = await ephemeral_backend.pop("m", key, 2, 4)

        assert result == blocks[2:]
        assert await ephemeral_backend.read("m", key, 0, 2) == blocks[:2]

    async def test_pop_returns_empty_for_already_popped_range(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        key = uuid.uuid4()
        await ephemeral_backend.append("m", key, TextEvent(channel="output", text="x"))
        await ephemeral_backend.pop("m", key, 0, 1)

        assert await ephemeral_backend.pop("m", key, 0, 1) == []

    async def test_pop_returns_empty_for_invalid_range(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        """``start >= end`` short-circuits without consulting the deque (early-exit branch)."""
        key = uuid.uuid4()
        await ephemeral_backend.append("m", key, TextEvent(channel="output", text="x"))

        assert await ephemeral_backend.pop("m", key, 5, 3) == []
        assert await ephemeral_backend.pop("m", key, 2, 2) == []

    async def test_append_blocks_when_capacity_full_and_resumes_on_pop(self) -> None:
        backend = InMemoryStreamsBackend(capacity=2)
        key = uuid.uuid4()
        for i in range(2):
            await backend.append("m", key, TextEvent(channel="output", text=f"t{i}"))

        pending = asyncio.create_task(backend.append("m", key, TextEvent(channel="output", text="t2")))
        await asyncio.sleep(0)

        assert not pending.done()

        await backend.pop("m", key, 0, 1)
        await asyncio.wait_for(pending, timeout=1.0)

        assert backend.length()[("m", key)] == 3

    async def test_append_blocks_resume_on_discard(self) -> None:
        backend = InMemoryStreamsBackend(capacity=1)
        key = uuid.uuid4()
        await backend.append("m", key, TextEvent(channel="output", text="t0"))

        pending = asyncio.create_task(backend.append("m", key, TextEvent(channel="output", text="t1")))
        await asyncio.sleep(0)
        assert not pending.done()

        await backend.discard("m", key)
        await asyncio.wait_for(pending, timeout=1.0)

        assert backend.length()[("m", key)] == 1

    async def test_len_aggregates_lengths(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        """``len(backend)`` aggregates per-key counts through the abstract ``__len__`` default."""
        ka, kb = uuid.uuid4(), uuid.uuid4()
        await ephemeral_backend.append("m", ka, TextEvent(channel="output", text="a"))
        await ephemeral_backend.append("m", kb, TextEvent(channel="output", text="b"))
        await ephemeral_backend.append("m", kb, TextEvent(channel="output", text="c"))

        assert len(ephemeral_backend) == 3

    async def test_length_tracks_per_key(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        key_a = uuid.uuid4()
        key_b = uuid.uuid4()
        await ephemeral_backend.append("m", key_a, TextEvent(channel="output", text="a"))
        await ephemeral_backend.append("m", key_a, TextEvent(channel="output", text="b"))
        await ephemeral_backend.append("other", key_b, TextEvent(channel="output", text="x"))

        lengths = ephemeral_backend.length()

        assert lengths[("m", key_a)] == 2
        assert lengths[("other", key_b)] == 1

    async def test_discard_drops_entry(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        key = uuid.uuid4()
        await ephemeral_backend.append("m", key, TextEvent(channel="output", text="x"))

        await ephemeral_backend.discard("m", key)

        assert await ephemeral_backend.read("m", key, 0, 10) == []
        assert ("m", key) not in ephemeral_backend.length()

    async def test_discard_unknown_is_noop(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        await ephemeral_backend.discard("missing", uuid.uuid4())

    async def test_usage_is_none(self, ephemeral_backend: InMemoryStreamsBackend) -> None:
        await ephemeral_backend.append("m", uuid.uuid4(), TextEvent(channel="output", text="x"))

        assert ephemeral_backend.usage() is None


class TestCaseStreamBuffer:
    """Cover :class:`StreamBuffer` end-to-end across the three supported backend compositions
    (durable + unbounded ephemeral, ephemeral-only, durable + capacity-bounded ephemeral) and the
    :meth:`load` producer-side drain used by serving layers.

    The default :meth:`buffer` fixture is the *persistent* shape (durable + unbounded ephemeral) so
    ``read`` is repeatable — ephemeral pops first, the durable backend refills any prefix that's
    already been consumed. The :meth:`ephemeral_only_buffer` and :meth:`bounded_buffer` fixtures
    cover the single-consumer (OpenAI Chat Completions, no disk I/O) and bounded-channel (producer
    backpressure) shapes respectively.
    """

    @pytest.fixture(scope="function")
    def buffer(self, backend: FileStreamsBackend, ephemeral_backend: InMemoryStreamsBackend) -> StreamBuffer:
        return StreamBuffer(model="m", id=uuid.uuid4(), ephemeral=ephemeral_backend, backend=backend)

    @pytest.fixture(scope="function")
    def ephemeral_only_buffer(self, ephemeral_backend: InMemoryStreamsBackend) -> StreamBuffer:
        return StreamBuffer(model="m", id=uuid.uuid4(), ephemeral=ephemeral_backend, backend=None)

    @pytest.fixture(scope="function")
    def bounded_buffer(self, backend: FileStreamsBackend) -> StreamBuffer:
        ephemeral = InMemoryStreamsBackend(capacity=2)
        return StreamBuffer(model="m", id=uuid.uuid4(), ephemeral=ephemeral, backend=backend)

    @pytest.mark.parametrize(
        ["use_durable_backend"],
        [
            pytest.param(True, id="durable_plus_unbounded_ephemeral"),
            pytest.param(False, id="ephemeral_only"),
        ],
    )
    def test_init(
        self,
        buffer: StreamBuffer,
        ephemeral_only_buffer: StreamBuffer,
        backend: FileStreamsBackend,
        ephemeral_backend: InMemoryStreamsBackend,
        use_durable_backend: bool,
    ) -> None:
        target = buffer if use_durable_backend else ephemeral_only_buffer

        assert target.length == 0
        assert target.done is False
        assert target.stop_reason is None
        assert target.ephemeral is ephemeral_backend
        if use_durable_backend:
            assert target.backend is backend
        else:
            assert target.backend is None

    @pytest.mark.parametrize(
        ["scenario"],
        [
            pytest.param("single_block", id="single_block"),
            pytest.param("multiple_blocks", id="multiple_blocks"),
            pytest.param("writes_through_both_backends", id="writes_through_both_backends"),
            pytest.param("signals_waiters", id="signals_waiters"),
            pytest.param("stop_reason_tracks_terminal_block", id="stop_reason_tracks_terminal_block"),
            pytest.param("accumulates_output_tokens_from_trace", id="accumulates_output_tokens_from_trace"),
            pytest.param("suspends_when_ephemeral_is_full", id="suspends_when_ephemeral_is_full"),
        ],
    )
    async def test_append(  # noqa: C901
        self,
        buffer: StreamBuffer,
        bounded_buffer: StreamBuffer,
        backend: FileStreamsBackend,
        ephemeral_backend: InMemoryStreamsBackend,
        scenario: str,
    ) -> None:
        if scenario == "single_block":
            blocks: list[Event] = [TextEvent(channel="output", text="hi")]
            for block in blocks:
                await buffer.append(block)
            assert buffer.length == len(blocks)
            assert await buffer.read(0, buffer.length) == blocks
        elif scenario == "multiple_blocks":
            blocks = [TextEvent(channel="output", text="hi"), TextEvent(channel="output", text="there")]
            for block in blocks:
                await buffer.append(block)
            assert buffer.length == len(blocks)
            assert await buffer.read(0, buffer.length) == blocks
        elif scenario == "writes_through_both_backends":
            await buffer.append(TextEvent(channel="output", text="x"))
            assert backend.length()[("m", buffer.id)] == 1
            assert ephemeral_backend.length()[("m", buffer.id)] == 1
        elif scenario == "signals_waiters":

            async def _wait() -> int:
                async with buffer._condition:
                    while buffer.length == 0:
                        await buffer._condition.wait()
                    return buffer.length

            task = asyncio.create_task(_wait())
            await asyncio.sleep(0)
            await buffer.append(TextEvent(channel="output", text="."))
            assert await task == 1
        elif scenario == "stop_reason_tracks_terminal_block":
            await buffer.append(TextEvent(channel="output", text="x"))
            assert buffer.stop_reason is None
            assert buffer.done is False
            await buffer.append(StopEvent(stop_reason="stop", output_tokens=2))
            assert buffer.done is True
            assert buffer.stop_reason == "stop"
        elif scenario == "accumulates_output_tokens_from_trace":
            await buffer.append(TraceEvent(token_count=3))
            await buffer.append(TraceEvent(token_count=5))
            assert buffer._output_tokens == 8
        elif scenario == "suspends_when_ephemeral_is_full":
            for i in range(2):
                await bounded_buffer.append(TextEvent(channel="output", text=f"t{i}"))
            pending = asyncio.create_task(bounded_buffer.append(TextEvent(channel="output", text="t2")))
            await asyncio.sleep(0)
            assert not pending.done()
            await bounded_buffer.read(0, 2)
            await asyncio.wait_for(pending, timeout=1.0)
            assert bounded_buffer.length == 3
        else:
            raise AssertionError(f"unknown scenario: {scenario}")

    @pytest.mark.parametrize(
        ["reason", "expected_reason"],
        [
            pytest.param(None, "error", id="default"),
            pytest.param("timeout", "timeout", id="custom"),
        ],
    )
    async def test_error_synthesises_stop_block_with_accumulated_output_tokens(
        self, buffer: StreamBuffer, reason: str | None, expected_reason: str
    ) -> None:
        await buffer.append(TraceEvent(token_count=2))

        if reason is None:
            await buffer.error()
        else:
            await buffer.error(reason)

        items = await buffer.read(0, buffer.length)
        assert isinstance(items[-1], StopEvent)
        assert items[-1].stop_reason == expected_reason
        assert items[-1].output_tokens == 2
        assert buffer.done is True
        assert buffer.stop_reason == expected_reason

    @pytest.mark.parametrize(
        ["scenario"],
        [
            pytest.param("full_range", id="full_range"),
            pytest.param("prefix", id="prefix"),
            pytest.param("suffix", id="suffix"),
            pytest.param("middle", id="middle"),
            pytest.param("past_length", id="past_length"),
            pytest.param("empty_range", id="empty_range"),
            pytest.param("pops_ephemeral_and_falls_back_to_backend", id="pops_ephemeral_and_falls_back_to_backend"),
            pytest.param("destructive_without_backend", id="destructive_without_backend"),
        ],
    )
    async def test_read(
        self,
        buffer: StreamBuffer,
        ephemeral_only_buffer: StreamBuffer,
        ephemeral_backend: InMemoryStreamsBackend,
        scenario: str,
    ) -> None:
        slicing_cases: dict[str, tuple[int, int, int, list[int]]] = {
            "full_range": (5, 0, 5, [0, 1, 2, 3, 4]),
            "prefix": (5, 0, 3, [0, 1, 2]),
            "suffix": (5, 2, 5, [2, 3, 4]),
            "middle": (5, 1, 4, [1, 2, 3]),
            "past_length": (2, 5, 8, []),
            "empty_range": (2, 1, 1, []),
        }
        if scenario in slicing_cases:
            written, start, end, expected_indices = slicing_cases[scenario]
            blocks = [TextEvent(channel="output", text=f"t{i}") for i in range(written)]
            for block in blocks:
                await buffer.append(block)
            assert await buffer.read(start, end) == [blocks[i] for i in expected_indices]
        elif scenario == "pops_ephemeral_and_falls_back_to_backend":
            for i in range(3):
                await buffer.append(TextEvent(channel="output", text=f"t{i}"))
            first = await buffer.read(0, 3)
            assert ephemeral_backend.length()[("m", buffer.id)] == 3
            assert await buffer.read(0, 0) == []
            second = await buffer.read(0, 3)
            assert first == second
            assert [t.cast(TextEvent, block).text for block in first] == ["t0", "t1", "t2"]
        elif scenario == "destructive_without_backend":
            for i in range(3):
                await ephemeral_only_buffer.append(TextEvent(channel="output", text=f"t{i}"))
            assert len(await ephemeral_only_buffer.read(0, 3)) == 3
            assert await ephemeral_only_buffer.read(0, 3) == []
        else:
            raise AssertionError(f"unknown scenario: {scenario}")

    @pytest.mark.parametrize(
        ["scenario"],
        [
            pytest.param("replays_completed_buffer", id="replays_completed_buffer"),
            pytest.param("tails_until_stop", id="tails_until_stop"),
            pytest.param("isolates_cursors_per_consumer", id="isolates_cursors_per_consumer"),
            pytest.param("drains_once_without_backend", id="drains_once_without_backend"),
        ],
    )
    async def test_aiter(  # noqa: C901
        self,
        buffer: StreamBuffer,
        ephemeral_only_buffer: StreamBuffer,
        scenario: str,
    ) -> None:
        if scenario == "replays_completed_buffer":
            blocks: list[Event] = [
                TextEvent(channel="output", text="a"),
                TextEvent(channel="output", text="b"),
                StopEvent(stop_reason="stop"),
            ]
            for block in blocks:
                await buffer.append(block)
            assert [b async for b in buffer] == blocks
        elif scenario == "tails_until_stop":

            async def _produce_late() -> None:
                await asyncio.sleep(0.01)
                await buffer.append(TextEvent(channel="output", text="late"))
                await buffer.append(StopEvent(stop_reason="stop"))

            producer = asyncio.create_task(_produce_late())
            try:
                collected = [b async for b in buffer]
            finally:
                await producer
            assert collected == [
                TextEvent(channel="output", text="late"),
                StopEvent(stop_reason="stop"),
            ]
        elif scenario == "isolates_cursors_per_consumer":

            async def _consume() -> list[Event]:
                return [b async for b in buffer]

            async def _produce_pair() -> None:
                await asyncio.sleep(0.01)
                await buffer.append(TextEvent(channel="output", text="x"))
                await buffer.append(TextEvent(channel="output", text="y"))
                await buffer.append(StopEvent(stop_reason="stop"))

            first = asyncio.create_task(_consume())
            second = asyncio.create_task(_consume())
            try:
                await _produce_pair()
                assert await first == await second
            finally:
                for task in (first, second):
                    if not task.done():
                        task.cancel()
        elif scenario == "drains_once_without_backend":
            await ephemeral_only_buffer.append(TextEvent(channel="output", text="a"))
            await ephemeral_only_buffer.append(StopEvent(stop_reason="stop"))
            first_read = [b async for b in ephemeral_only_buffer]
            second_read = [b async for b in ephemeral_only_buffer]
            assert len(first_read) == 2
            assert second_read == []
        else:
            raise AssertionError(f"unknown scenario: {scenario}")

    @pytest.mark.parametrize(
        ["scenario"],
        [
            pytest.param("normal_completion", id="normal_completion"),
            pytest.param("generic_exception_terminates", id="generic_exception_terminates"),
            pytest.param("framework_not_installed_terminates", id="framework_not_installed_terminates"),
            pytest.param(
                "synthesises_error_block_with_accumulated_output_tokens",
                id="synthesises_error_block_with_accumulated_output_tokens",
            ),
            pytest.param(
                "logs_framework_not_installed_without_traceback",
                id="logs_framework_not_installed_without_traceback",
            ),
            pytest.param("logs_generic_exception_with_traceback", id="logs_generic_exception_with_traceback"),
        ],
    )
    async def test_load(
        self,
        buffer: StreamBuffer,
        caplog: pytest.LogCaptureFixture,
        scenario: str,
    ) -> None:
        terminate_cases: dict[str, tuple[Exception | None, str]] = {
            "normal_completion": (None, "stop"),
            "generic_exception_terminates": (RuntimeError("boom"), "error"),
            "framework_not_installed_terminates": (FrameworkNotInstalled("torch"), "error"),
        }

        if scenario in terminate_cases:
            error, expected_stop_reason = terminate_cases[scenario]

            async def _stream() -> t.AsyncIterator[Event]:
                yield StartEvent(id=str(buffer.id), created=0, input_tokens=7)
                yield TextEvent(channel="output", text="a")
                yield TextEvent(channel="output", text="b")
                if error is not None:
                    raise error
                yield StopEvent(stop_reason="stop", output_tokens=0)

            await buffer.load(_stream())
            items = await buffer.read(0, buffer.length)
            assert buffer.done is True
            assert buffer.stop_reason == expected_stop_reason
            stops = [b for b in items if isinstance(b, StopEvent)]
            assert stops and stops[-1].stop_reason == expected_stop_reason
        elif scenario == "synthesises_error_block_with_accumulated_output_tokens":

            async def _stream() -> t.AsyncIterator[Event]:
                yield StartEvent(id=str(buffer.id), created=0, input_tokens=3)
                yield TraceEvent(token_count=5)
                yield TraceEvent(token_count=2)
                raise RuntimeError("boom")

            await buffer.load(_stream())
            items = await buffer.read(0, buffer.length)
            stops = [b for b in items if isinstance(b, StopEvent)]
            assert stops[-1].stop_reason == "error"
            assert stops[-1].output_tokens == 7
        elif scenario == "logs_framework_not_installed_without_traceback":

            async def _stream() -> t.AsyncIterator[Event]:
                yield StartEvent(id=str(buffer.id), created=0)
                raise FrameworkNotInstalled("torch")

            with caplog.at_level("ERROR"):
                await buffer.load(_stream())
            records = [r for r in caplog.records if "missing dependency" in r.getMessage()]
            assert records and records[-1].exc_info is None
        elif scenario == "logs_generic_exception_with_traceback":

            async def _stream() -> t.AsyncIterator[Event]:
                yield StartEvent(id=str(buffer.id), created=0)
                raise RuntimeError("boom")

            with caplog.at_level("ERROR"):
                await buffer.load(_stream())
            records = [r for r in caplog.records if "generation failed" in r.getMessage()]
            assert records and records[-1].exc_info is not None
        else:
            raise AssertionError(f"unknown scenario: {scenario}")


class TestCaseModelStreams:
    """Cover :class:`ModelStreams` allocation, indexing, and removal for one model namespace."""

    @pytest.fixture(scope="function")
    def streams(self, backend: FileStreamsBackend, ephemeral_backend: InMemoryStreamsBackend) -> ModelStreams:
        return ModelStreams("m", backend, ephemeral_backend)

    def test_init(
        self, streams: ModelStreams, backend: FileStreamsBackend, ephemeral_backend: InMemoryStreamsBackend
    ) -> None:
        assert streams.name == "m"
        assert streams._backend is backend
        assert streams._ephemeral_backend is ephemeral_backend
        assert len(streams) == 0
        assert list(streams) == []

    async def test_create_returns_wired_buffer(
        self, streams: ModelStreams, backend: FileStreamsBackend, ephemeral_backend: InMemoryStreamsBackend
    ) -> None:
        buffer_id, buffer = await streams.create()

        assert isinstance(buffer_id, uuid.UUID)
        assert isinstance(buffer, StreamBuffer)
        assert buffer.model == "m"
        assert buffer.id == buffer_id
        assert buffer.backend is backend
        assert buffer.ephemeral is ephemeral_backend
        assert streams[buffer_id] is buffer
        assert buffer_id in streams
        assert len(streams) == 1

    async def test_create_ephemeral_drops_durable_backend(
        self, streams: ModelStreams, ephemeral_backend: InMemoryStreamsBackend
    ) -> None:
        buffer_id, buffer = await streams.create(persist=False)

        assert buffer.backend is None
        assert buffer.ephemeral is ephemeral_backend
        assert streams[buffer_id] is buffer

    @pytest.mark.parametrize(
        ["existing", "exception"],
        [
            pytest.param(True, None, id="existing"),
            pytest.param(False, KeyError, id="missing_raises"),
        ],
        indirect=["exception"],
    )
    async def test_getitem(self, streams: ModelStreams, existing: bool, exception) -> None:
        target_id, target = await streams.create() if existing else (uuid.uuid4(), None)

        with exception:
            assert streams[target_id] is target

    @pytest.mark.parametrize(
        ["existing"],
        [pytest.param(True, id="existing"), pytest.param(False, id="missing")],
    )
    async def test_remove(self, streams: ModelStreams, existing: bool) -> None:
        target_id, target = await streams.create() if existing else (uuid.uuid4(), None)

        result = await streams.remove(target_id)

        assert result is target
        assert target_id not in streams

    async def test_remove_discards_both_backends(
        self,
        streams: ModelStreams,
        backend: FileStreamsBackend,
        ephemeral_backend: InMemoryStreamsBackend,
    ) -> None:
        buffer_id, _ = await streams.create()
        await streams[buffer_id].append(TextEvent(channel="output", text="hi"))
        assert (streams.name, buffer_id) in backend.length()
        assert (streams.name, buffer_id) in ephemeral_backend.length()

        await streams.remove(buffer_id)

        assert (streams.name, buffer_id) not in backend.length()
        assert (streams.name, buffer_id) not in ephemeral_backend.length()

    async def test_remove_ephemeral_buffer_clears_in_memory_backend(
        self, streams: ModelStreams, ephemeral_backend: InMemoryStreamsBackend
    ) -> None:
        buffer_id, _ = await streams.create(persist=False)
        await streams[buffer_id].append(TextEvent(channel="output", text="hi"))
        assert (streams.name, buffer_id) in ephemeral_backend.length()

        await streams.remove(buffer_id)

        assert (streams.name, buffer_id) not in ephemeral_backend.length()

    async def test_iter_yields_pairs(self, streams: ModelStreams) -> None:
        a_id, a = await streams.create()
        b_id, b = await streams.create()

        assert dict(streams) == {a_id: a, b_id: b}


class TestCaseStreamsRegistry:
    """Cover :class:`StreamsRegistry` lifecycle, model registration, and cleanup wire-in."""

    async def test_init(self, backend: FileStreamsBackend, ephemeral_backend: InMemoryStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend, ephemeral_backend=ephemeral_backend)

        assert len(registry) == 0
        assert registry.backend is backend
        assert registry.ephemeral_backend is ephemeral_backend
        assert registry.cleanup_task is None

    async def test_init_defaults_to_file_and_capacity_bounded_in_memory_backends(self) -> None:
        registry = StreamsRegistry()

        assert isinstance(registry.backend, FileStreamsBackend)
        assert isinstance(registry.ephemeral_backend, InMemoryStreamsBackend)
        # The default ephemeral backend is bounded so producer backpressure is on out-of-the-box.
        assert registry.ephemeral_backend.capacity is not None

    async def test_aopen_aclose_are_idempotent(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)

        await registry.aopen()
        await registry.aopen()
        await registry.aclose()
        await registry.aclose()

    async def test_aopen_aclose_drives_both_backends(self) -> None:
        persistent = MagicMock(spec=StreamsBackend)
        persistent.aopen = AsyncMock()
        persistent.aclose = AsyncMock()
        ephemeral = MagicMock(spec=StreamsBackend)
        ephemeral.aopen = AsyncMock()
        ephemeral.aclose = AsyncMock()
        registry = StreamsRegistry(backend=persistent, ephemeral_backend=ephemeral)

        await registry.aopen()
        await registry.aclose()

        assert persistent.aopen.await_count == 1
        assert ephemeral.aopen.await_count == 1
        assert persistent.aclose.await_count == 1
        assert ephemeral.aclose.await_count == 1

    async def test_async_context_manager(self, tmp_path: pathlib.Path) -> None:
        async with StreamsRegistry(backend=FileStreamsBackend(path=tmp_path, remove=False)) as registry:
            assert len(registry) == 0

    async def test_aopen_starts_cleanup_task(self, backend: FileStreamsBackend) -> None:
        cleanup = MagicMock(spec=CleanupTask)
        cleanup.start = AsyncMock()
        cleanup.stop = AsyncMock()
        registry = StreamsRegistry(backend=backend, cleanup=cleanup)

        await registry.aopen()
        await registry.aclose()

        assert cleanup.start.await_args_list == [call(registry)]
        assert cleanup.stop.await_count == 1

    async def test_add_returns_wired_handle(
        self, backend: FileStreamsBackend, ephemeral_backend: InMemoryStreamsBackend
    ) -> None:
        registry = StreamsRegistry(backend=backend, ephemeral_backend=ephemeral_backend)

        streams = registry.add("m")

        assert isinstance(streams, ModelStreams)
        assert streams.name == "m"
        assert streams._backend is backend
        assert streams._ephemeral_backend is ephemeral_backend
        assert "m" in registry
        assert registry["m"] is streams

    async def test_add_is_idempotent(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)

        first = registry.add("m")
        second = registry.add("m")

        assert first is second

    async def test_getitem_unknown_model_raises(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)

        with pytest.raises(KeyError):
            _ = registry["missing"]

    @pytest.mark.parametrize(
        ["existing"],
        [pytest.param(True, id="existing"), pytest.param(False, id="missing")],
    )
    async def test_remove_delegates_to_model_streams(self, backend: FileStreamsBackend, existing: bool) -> None:
        registry = StreamsRegistry(backend=backend)
        streams = registry.add("m")
        target_id, target = await streams.create() if existing else (uuid.uuid4(), None)

        result = await registry.remove("m", target_id)

        assert result is target
        assert target_id not in streams

    async def test_remove_unknown_model_returns_none(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)

        assert await registry.remove("missing", uuid.uuid4()) is None

    async def test_iter_yields_triples_across_models(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)
        await registry.add("a").create()
        await registry.add("b").create()

        entries = list(registry)

        assert len(entries) == 2
        models = {entry[0] for entry in entries}
        assert models == {"a", "b"}

    async def test_isolation_between_models(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)
        streams_a = registry.add("a")
        streams_b = registry.add("b")
        a_id, _ = await streams_a.create()

        assert a_id in streams_a
        assert a_id not in streams_b
        assert len(registry) == 1


class TestCaseCleanupTask:
    """Cover :class:`CleanupTask` policy combinations, lifecycle, and registry integration."""

    @pytest.mark.parametrize(
        ["ttl", "disk_usage", "period", "exception"],
        [
            pytest.param(10.0, None, 60.0, None, id="ttl_only"),
            pytest.param(None, 1024, 60.0, None, id="disk_only"),
            pytest.param(10.0, 1024, 60.0, None, id="both"),
            pytest.param(None, None, 60.0, (ValueError, "ttl"), id="no_signal_raises"),
            pytest.param(10.0, None, 0, (ValueError, "period"), id="period_zero_raises"),
            pytest.param(10.0, None, -1.0, (ValueError, "period"), id="period_negative_raises"),
        ],
        indirect=["exception"],
    )
    def test_init(self, ttl: float | None, disk_usage: int | None, period: float, exception) -> None:
        with exception:
            CleanupTask(ttl=ttl, disk_usage=disk_usage, period=period)

    async def test_evict_by_ttl(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)
        streams = registry.add("m")
        stale_id, stale = await streams.create()
        stale.timestamp = time.monotonic() - 100.0
        fresh_id, _ = await streams.create()
        task = CleanupTask(ttl=10.0)

        evicted = await task.evict(registry)

        assert evicted == [("m", stale_id)]
        assert stale_id not in streams
        assert fresh_id in streams

    async def test_evict_by_disk_usage_done_first(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)
        streams = registry.add("m")
        # Persist enough bytes so the disk-usage policy fires even with a tiny budget. Active buffers are never
        # candidates so they survive even when older; the older done buffer is dropped before the newer one.
        active_id, active = await streams.create()
        await active.append(TextEvent(channel="output", text="active"))
        active.timestamp = time.monotonic() - 200.0

        old_done_id, old_done = await streams.create()
        await old_done.append(StopEvent(stop_reason="stop"))
        old_done.timestamp = time.monotonic() - 100.0

        new_done_id, new_done = await streams.create()
        await new_done.append(StopEvent(stop_reason="stop"))

        task = CleanupTask(disk_usage=1)

        evicted = await task.evict(registry)

        assert ("m", old_done_id) in evicted
        assert ("m", active_id) not in evicted
        if ("m", new_done_id) in evicted:
            assert evicted.index(("m", old_done_id)) < evicted.index(("m", new_done_id))

    async def test_evict_no_op_when_under_disk_budget(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)
        await registry.add("m").create()
        task = CleanupTask(disk_usage=1 << 30)

        assert await task.evict(registry) == []
        assert len(registry) == 1

    async def test_evict_by_disk_usage_breaks_once_under_budget(self, backend: FileStreamsBackend) -> None:
        """The eviction loop stops as soon as the cumulative budget drops at-or-below the limit."""
        registry = StreamsRegistry(backend=backend)
        streams = registry.add("m")
        # Two done buffers with substantial payloads; budget tuned so a single eviction is enough to satisfy it.
        old_id, old = await streams.create()
        await old.append(TextEvent(channel="output", text="x" * 1024))
        await old.append(StopEvent(stop_reason="stop"))
        old.timestamp = time.monotonic() - 100.0

        new_id, new = await streams.create()
        await new.append(TextEvent(channel="output", text="y" * 1024))
        await new.append(StopEvent(stop_reason="stop"))
        new.timestamp = time.monotonic() - 10.0

        usage = registry.backend.usage()
        assert usage is not None
        # Set the budget between one buffer's size and both combined so the loop breaks after the first eviction.
        single = usage[("m", old_id)]
        total = sum(usage.values())
        task = CleanupTask(disk_usage=(single + total) // 2)

        evicted = await task.evict(registry)

        assert evicted == [("m", old_id)]
        assert ("m", new_id) in {(m, k) for (m, k, _) in registry}

    async def test_evict_ignores_backend_without_usage(self) -> None:
        class _NoUsageBackend(StreamsBackend):
            def length(self) -> dict[tuple[str, uuid.UUID], int]:
                return {}

            async def append(self, model, key, block):  # noqa: ARG002
                return None

            async def read(self, model, key, start, end):  # noqa: ARG002
                return []

            async def pop(self, model, key, start, end):  # noqa: ARG002
                return []

            async def discard(self, model, key):  # noqa: ARG002
                return None

            def usage(self):
                return None

        registry = StreamsRegistry(backend=_NoUsageBackend())
        task = CleanupTask(disk_usage=1)

        # Synthesize an entry without going through ``create`` to keep the test focused on the policy branch.
        registry.add("m")._buffers[uuid.uuid4()] = MagicMock(spec=StreamBuffer, done=True, timestamp=time.monotonic())

        assert await task.evict(registry) == []
        assert len(registry) == 1

    async def test_start_stop_are_idempotent(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)
        task = CleanupTask(ttl=10.0, period=0.01)

        await task.start(registry)
        await task.start(registry)
        await task.stop()
        await task.stop()

    async def test_background_loop_calls_evict(self, backend: FileStreamsBackend) -> None:
        registry = StreamsRegistry(backend=backend)
        task = CleanupTask(ttl=0.001, period=0.005)
        streams = registry.add("m")
        stale_id, stale = await streams.create()
        stale.timestamp = time.monotonic() - 100.0

        await task.start(registry)
        try:
            for _ in range(50):
                if stale_id not in streams:
                    break
                await asyncio.sleep(0.01)
        finally:
            await task.stop()

        assert stale_id not in streams

    async def test_background_loop_survives_evict_failure(
        self, backend: FileStreamsBackend, caplog: pytest.LogCaptureFixture
    ) -> None:
        registry = StreamsRegistry(backend=backend)
        task = CleanupTask(ttl=10.0, period=0.005)

        calls: list[int] = []

        async def _flaky(_registry: StreamsRegistry) -> list[tuple[str, uuid.UUID]]:
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("transient")
            return []

        task.evict = _flaky  # type: ignore[method-assign]

        with caplog.at_level("ERROR"):
            await task.start(registry)
            try:
                for _ in range(50):
                    if len(calls) >= 2:
                        break
                    await asyncio.sleep(0.01)
            finally:
                await task.stop()

        assert len(calls) >= 2
        assert any("cleanup pass failed" in record.getMessage().lower() for record in caplog.records)

    async def test_registry_aopen_starts_and_aclose_stops_real_task(self, backend: FileStreamsBackend) -> None:
        task = CleanupTask(ttl=10.0, period=0.005)
        registry = StreamsRegistry(backend=backend, cleanup=task)

        await registry.aopen()
        assert task._task is not None
        await registry.aclose()
        assert task._task is None
