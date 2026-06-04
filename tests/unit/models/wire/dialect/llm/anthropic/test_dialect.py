import json
import typing as t
import uuid

import pytest

from flama.http.responses.sse import ServerSentEvent
from flama.models.exceptions import LLMGenerationError
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect.llm.anthropic import (
    AnthropicAssembler,
    AnthropicDialect,
    AnthropicParser,
    AnthropicRenderer,
)

_GEN_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def _events() -> list:
    return [
        StartEvent(id="msg-1", created=1000, input_tokens=4),
        TextEvent(channel="thinking", text="reasoning"),
        TextEvent(channel="output", text="answer"),
        ToolEvent(id="c1", name="lookup", arguments={"q": "x"}),
        StopEvent(stop_reason="tool_use", output_tokens=8),
    ]


def _error_events() -> list:
    return [
        StartEvent(id="msg-1", created=1000),
        StopEvent(stop_reason="error"),
    ]


def _verify_render(frames: list[ServerSentEvent]) -> None:
    events = [f.event for f in frames]
    assert events[0] == "message_start"
    assert events[-1] == "message_stop"
    assert "content_block_start" in events
    assert "content_block_delta" in events
    assert "message_delta" in events
    started = next(f for f in frames if f.event == "message_start")
    body = json.loads(started.data)
    assert body["message"]["id"].startswith("msg_")
    assert _GEN_ID.hex in body["message"]["id"]


def _verify_assemble(envelope: dict[str, t.Any]) -> None:
    assert envelope["type"] == "message"
    assert envelope["model"] == "m"
    assert envelope["id"].startswith("msg_")
    assert _GEN_ID.hex in envelope["id"]
    types_in_order = [block["type"] for block in envelope["content"]]
    assert types_in_order == ["thinking", "text", "tool_use"]
    assert envelope["stop_reason"] == "tool_use"
    assert envelope["usage"] == {"input_tokens": 4, "output_tokens": 8}


class TestCaseAnthropicDialect:
    """Cover :class:`AnthropicDialect` end-to-end: strategy bindings, the :meth:`render` façade, and the
    :meth:`assemble` envelope construction.
    """

    @pytest.mark.parametrize(
        ["attr", "expected"],
        [
            pytest.param("PARSER", AnthropicParser, id="parser"),
            pytest.param("RENDERER", AnthropicRenderer, id="renderer"),
            pytest.param("ASSEMBLER", AnthropicAssembler, id="assembler"),
        ],
    )
    def test_bindings(self, attr: str, expected: type) -> None:
        assert getattr(AnthropicDialect, attr) is expected

    async def test_render(self) -> None:
        frames = [frame async for frame in AnthropicDialect.render(_events(), model="m", generation_id=_GEN_ID)]

        _verify_render(frames)

    async def test_assemble(self) -> None:
        envelope = await AnthropicDialect.assemble(_events(), model="m", generation_id=_GEN_ID)

        _verify_assemble(envelope)

    async def test_assemble_raises_llm_generation_error(self) -> None:
        with pytest.raises(LLMGenerationError, match="LLM stream generation failed"):
            await AnthropicDialect.assemble(_error_events(), model="m", generation_id=_GEN_ID)
