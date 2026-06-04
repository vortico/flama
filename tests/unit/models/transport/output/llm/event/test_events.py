import dataclasses
import typing as t

import pytest

from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent


class TestCaseEvent:
    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            Event()  # type: ignore[abstract]


class TestCaseTextEvent:
    @pytest.mark.parametrize(
        ["channel", "text", "payload", "delta"],
        [
            pytest.param(
                "output",
                "hello",
                {"type": "text", "channel": "output", "text": "hello"},
                {"type": "text.delta", "text": "hello"},
                id="output",
            ),
            pytest.param(
                "thinking",
                "",
                {"type": "text", "channel": "thinking", "text": ""},
                {"type": "text.delta", "text": ""},
                id="empty_thinking",
            ),
        ],
    )
    def test_payload(self, channel: str, text: str, payload: dict[str, t.Any], delta: dict[str, t.Any]) -> None:
        block = TextEvent(channel=channel, text=text)

        assert isinstance(block, Event)
        assert block.payload() == payload
        assert block.delta_payload() == delta

    def test_is_frozen(self) -> None:
        block = TextEvent(channel="output", text="x")

        with pytest.raises(dataclasses.FrozenInstanceError):
            block.channel = "other"  # type: ignore[misc]


class TestCaseToolEvent:
    @pytest.mark.parametrize(
        ["id_", "name", "arguments", "payload", "delta"],
        [
            pytest.param(
                "call_1",
                "fn",
                {"a": 1},
                {"type": "tool", "id": "call_1", "name": "fn", "arguments": {"a": 1}},
                {"type": "tool.delta", "name": "fn", "arguments": {"a": 1}},
                id="with_args",
            ),
            pytest.param(
                "call_2",
                "noop",
                {},
                {"type": "tool", "id": "call_2", "name": "noop", "arguments": {}},
                {"type": "tool.delta", "name": "noop", "arguments": {}},
                id="empty_args",
            ),
        ],
    )
    def test_payload(
        self,
        id_: str,
        name: str,
        arguments: dict[str, t.Any],
        payload: dict[str, t.Any],
        delta: dict[str, t.Any],
    ) -> None:
        block = ToolEvent(id=id_, name=name, arguments=arguments)

        assert isinstance(block, Event)
        assert block.payload() == payload
        assert block.delta_payload() == delta

    def test_is_frozen(self) -> None:
        block = ToolEvent(id="call_1", name="fn", arguments={})

        with pytest.raises(dataclasses.FrozenInstanceError):
            block.name = "other"  # type: ignore[misc]


class TestCaseTraceEvent:
    @pytest.mark.parametrize(
        ["token_count", "finish_reason"],
        [
            pytest.param(None, None, id="empty"),
            pytest.param(1, None, id="token_count_only"),
            pytest.param(None, "stop", id="finish_reason_only"),
            pytest.param(10, "tool_calls", id="full"),
        ],
    )
    def test_init(self, token_count: int | None, finish_reason: str | None) -> None:
        trace = TraceEvent(token_count=token_count, finish_reason=finish_reason)

        assert isinstance(trace, Event)
        assert trace.token_count == token_count
        assert trace.finish_reason == finish_reason
        assert trace.payload() == {"token_count": token_count, "finish_reason": finish_reason}

    def test_is_frozen(self) -> None:
        trace = TraceEvent(token_count=1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            trace.token_count = 2  # type: ignore[misc]


class TestCaseStartEvent:
    @pytest.mark.parametrize(
        ["input_tokens", "expected"],
        [
            pytest.param(None, {"id": "abc", "created": 42}, id="no_input_tokens"),
            pytest.param(5, {"id": "abc", "created": 42, "input_tokens": 5}, id="with_input_tokens"),
        ],
    )
    def test_payload(self, input_tokens: int | None, expected: dict[str, t.Any]) -> None:
        block = StartEvent(id="abc", created=42, input_tokens=input_tokens)

        assert isinstance(block, Event)
        assert block.payload() == expected
        assert block.delta_payload() == expected

    def test_is_frozen(self) -> None:
        block = StartEvent(id="abc", created=42)

        with pytest.raises(dataclasses.FrozenInstanceError):
            block.id = "other"  # type: ignore[misc]


class TestCaseStopEvent:
    @pytest.mark.parametrize(
        ["stop_reason", "output_tokens", "expected"],
        [
            pytest.param(None, None, {}, id="empty"),
            pytest.param("stop", None, {"stop_reason": "stop"}, id="stop_reason_only"),
            pytest.param(None, 2, {"output_tokens": 2}, id="output_tokens_only"),
            pytest.param(
                "stop",
                2,
                {"stop_reason": "stop", "output_tokens": 2},
                id="full",
            ),
        ],
    )
    def test_payload(self, stop_reason: str | None, output_tokens: int | None, expected: dict[str, t.Any]) -> None:
        block = StopEvent(stop_reason=stop_reason, output_tokens=output_tokens)

        assert isinstance(block, Event)
        assert block.payload() == expected

    def test_is_frozen(self) -> None:
        block = StopEvent()

        with pytest.raises(dataclasses.FrozenInstanceError):
            block.stop_reason = "x"  # type: ignore[misc]


class TestCaseEventDict:
    """Cover :meth:`Event.to_dict` / :meth:`Event.from_dict` round-trip for every concrete :class:`Event`."""

    @pytest.mark.parametrize(
        ["block"],
        [
            pytest.param(TextEvent(channel="output", text="hello"), id="text"),
            pytest.param(TextEvent(channel="thinking", text=""), id="text_empty"),
            pytest.param(ToolEvent(id="call_1", name="fn", arguments={"a": 1}), id="tool"),
            pytest.param(ToolEvent(id="call_2", name="noop", arguments={}), id="tool_no_args"),
            pytest.param(TraceEvent(), id="trace_empty"),
            pytest.param(TraceEvent(token_count=5, finish_reason="stop"), id="trace_full"),
            pytest.param(StartEvent(id="abc", created=42), id="start"),
            pytest.param(StartEvent(id="abc", created=42, input_tokens=11), id="start_with_input_tokens"),
            pytest.param(StopEvent(), id="stop_empty"),
            pytest.param(StopEvent(stop_reason="stop", output_tokens=2), id="stop_full"),
        ],
    )
    def test_round_trip(self, block: Event) -> None:
        serialised = block.to_dict()

        assert "kind" in serialised
        assert serialised["kind"] == block.KIND
        assert Event.from_dict(serialised) == block

    def test_from_dict_unknown_kind_raises(self) -> None:
        with pytest.raises(KeyError):
            Event.from_dict({"kind": "unknown"})
