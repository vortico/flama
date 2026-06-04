import typing as t
import uuid

import pytest

from flama.models.transport.output.llm.event import Event, StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect.llm.anthropic.assembler import AnthropicAssembler

_GEN_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def _verify_text_only(envelope: dict[str, t.Any]) -> None:
    assert envelope["type"] == "message"
    assert envelope["role"] == "assistant"
    assert envelope["model"] == "m"
    assert envelope["id"].startswith("msg_")
    assert envelope["id"].endswith(_GEN_ID.hex)
    assert envelope["content"] == [{"type": "text", "text": "hello"}]
    assert envelope["stop_reason"] == "end_turn"
    assert envelope["stop_sequence"] is None
    assert envelope["usage"] == {"input_tokens": 4, "output_tokens": 5}


def _verify_text_with_thinking(envelope: dict[str, t.Any]) -> None:
    types_in_order = [block["type"] for block in envelope["content"]]
    assert types_in_order == ["thinking", "text"]
    assert envelope["content"][0]["thinking"] == "reasoning"
    assert envelope["content"][1]["text"] == "answer"


def _verify_tool_use_with_text(envelope: dict[str, t.Any]) -> None:
    types_in_order = [block["type"] for block in envelope["content"]]
    assert types_in_order == ["text", "tool_use"]
    tool = envelope["content"][1]
    assert tool == {"type": "tool_use", "id": "c1", "name": "lookup", "input": {"q": "x"}}
    assert envelope["stop_reason"] == "tool_use"


def _verify_tool_use_with_thinking_and_text(envelope: dict[str, t.Any]) -> None:
    types_in_order = [block["type"] for block in envelope["content"]]
    assert types_in_order == ["thinking", "text", "tool_use"]


def _verify_max_tokens(envelope: dict[str, t.Any]) -> None:
    assert envelope["stop_reason"] == "max_tokens"


def _verify_unknown_falls_back_to_end_turn(envelope: dict[str, t.Any]) -> None:
    assert envelope["stop_reason"] == "end_turn"


class TestCaseAnthropicAssembler:
    """Cover :meth:`AnthropicAssembler.envelope`.

    Drives the L2 -> Anthropic Messages buffered envelope strategy across the supported content shapes
    (text-only, thinking + text, tool_use ordering relative to text/thinking) and the stop-reason mapping.
    """

    @pytest.mark.parametrize(
        ["events", "start", "stop", "verify"],
        [
            pytest.param(
                (TextEvent(channel="output", text="hello"),),
                StartEvent(id="m", created=1, input_tokens=4),
                StopEvent(stop_reason="stop", output_tokens=5),
                _verify_text_only,
                id="text_only",
            ),
            pytest.param(
                (
                    TextEvent(channel="thinking", text="reasoning"),
                    TextEvent(channel="output", text="answer"),
                ),
                StartEvent(id="m", created=1, input_tokens=4),
                StopEvent(stop_reason="stop", output_tokens=5),
                _verify_text_with_thinking,
                id="text_with_thinking",
            ),
            pytest.param(
                (
                    TextEvent(channel="output", text="thinking before tool"),
                    ToolEvent(id="c1", name="lookup", arguments={"q": "x"}),
                ),
                StartEvent(id="m", created=1),
                StopEvent(stop_reason="tool_use"),
                _verify_tool_use_with_text,
                id="tool_use_with_text",
            ),
            pytest.param(
                (
                    TextEvent(channel="thinking", text="t"),
                    TextEvent(channel="output", text="o"),
                    ToolEvent(id="c1", name="lookup", arguments={}),
                ),
                StartEvent(id="m", created=1),
                StopEvent(stop_reason="tool_use"),
                _verify_tool_use_with_thinking_and_text,
                id="tool_use_with_thinking_and_text",
            ),
            pytest.param(
                (TextEvent(channel="output", text="x"),),
                StartEvent(id="m", created=0),
                StopEvent(stop_reason="max_tokens"),
                _verify_max_tokens,
                id="stop_reason_max_tokens",
            ),
            pytest.param(
                (TextEvent(channel="output", text="x"),),
                StartEvent(id="m", created=0),
                StopEvent(stop_reason="unknown"),
                _verify_unknown_falls_back_to_end_turn,
                id="stop_reason_unknown_falls_back_to_end_turn",
            ),
        ],
    )
    def test_envelope(
        self,
        events: tuple[Event, ...],
        start: StartEvent,
        stop: StopEvent,
        verify: t.Callable[[dict[str, t.Any]], None],
    ) -> None:
        envelope = AnthropicAssembler.envelope(events, start=start, stop=stop, model="m", generation_id=_GEN_ID)

        verify(envelope)

    def test_envelope_without_generation_id_falls_back_to_random(self) -> None:
        envelope = AnthropicAssembler.envelope(
            (TextEvent(channel="output", text="x"),),
            start=StartEvent(id="m", created=0),
            stop=StopEvent(stop_reason="stop"),
            model="m",
        )

        assert envelope["id"].startswith("msg_")
