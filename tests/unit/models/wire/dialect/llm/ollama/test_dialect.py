import typing as t

import pytest

from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect.llm.ollama import OllamaAssembler, OllamaDialect, OllamaParser, OllamaRenderer


def _chat_events() -> list:
    return [
        StartEvent(id="msg-1", created=1000, input_tokens=4),
        TextEvent(channel="output", text="Hello"),
        ToolEvent(id="call-1", name="lookup", arguments={"q": "x"}),
        StopEvent(stop_reason="stop", output_tokens=8),
    ]


def _generate_events() -> list:
    return [
        StartEvent(id="msg-1", created=2000, input_tokens=3),
        TextEvent(channel="output", text="World"),
        StopEvent(stop_reason="stop", output_tokens=5),
    ]


def _verify_chat_render(chunks: list[dict[str, t.Any]]) -> None:
    assert all(isinstance(chunk, dict) for chunk in chunks)
    assert all(chunk["model"] == "m" for chunk in chunks if "model" in chunk)
    terminal = chunks[-1]
    assert terminal["done"] is True
    assert terminal["message"]["content"] == ""
    assert terminal["done_reason"] == "stop"
    text_chunks = [c for c in chunks if c.get("message", {}).get("content")]
    assert any(c["message"]["content"] == "Hello" for c in text_chunks)
    tool_chunks = [c for c in chunks if c.get("message", {}).get("tool_calls")]
    assert tool_chunks
    assert tool_chunks[0]["message"]["tool_calls"][0]["function"]["name"] == "lookup"


def _verify_generate_render(chunks: list[dict[str, t.Any]]) -> None:
    assert any(chunk.get("response") == "World" for chunk in chunks)
    terminal = chunks[-1]
    assert terminal["done"] is True
    assert terminal["response"] == ""
    assert terminal["done_reason"] == "stop"


def _verify_chat_assemble(envelope: dict[str, t.Any]) -> None:
    assert envelope["model"] == "m"
    assert envelope["done"] is True
    assert envelope["done_reason"] == "stop"
    assert envelope["message"]["role"] == "assistant"
    assert envelope["message"]["content"] == "Hello"
    assert envelope["message"]["tool_calls"][0]["function"]["name"] == "lookup"
    assert envelope["message"]["tool_calls"][0]["function"]["arguments"] == {"q": "x"}
    assert envelope["prompt_eval_count"] == 4
    assert envelope["eval_count"] == 8


def _verify_chat_assemble_drops_tool_calls(envelope: dict[str, t.Any]) -> None:
    assert "tool_calls" not in envelope["message"]


def _verify_generate_assemble(envelope: dict[str, t.Any]) -> None:
    assert envelope["model"] == "m"
    assert envelope["done"] is True
    assert envelope["done_reason"] == "stop"
    assert envelope["response"] == "World"
    assert envelope["prompt_eval_count"] == 3
    assert envelope["eval_count"] == 5


def _make_thinking_verifier(
    expected_content: str, expected_thinking: str | None
) -> t.Callable[[dict[str, t.Any]], None]:
    def _verify(envelope: dict[str, t.Any]) -> None:
        assert envelope["message"]["content"] == expected_content
        if expected_thinking is None:
            assert "thinking" not in envelope["message"]
        else:
            assert envelope["message"]["thinking"] == expected_thinking

    return _verify


_TEXT_ONLY_CHAT = [
    StartEvent(id="msg-1", created=1000),
    TextEvent(channel="output", text="hi"),
    StopEvent(stop_reason="stop"),
]
_NAMED_THINKING_CHAT = [
    StartEvent(id="m", created=0),
    TextEvent(channel="thinking", text="r1"),
    TextEvent(channel="thinking", text="r2"),
    TextEvent(channel="output", text="answer"),
    StopEvent(stop_reason="stop"),
]
_OTHER_NAMED_CHANNEL_CHAT = [
    StartEvent(id="m", created=0),
    TextEvent(channel="analysis", text="meta"),
    TextEvent(channel="output", text="answer"),
    StopEvent(stop_reason="stop"),
]
_UNNAMED_CAPTURE_CHAT = [
    StartEvent(id="m", created=0),
    TextEvent(channel=None, text="quiet"),
    TextEvent(channel="output", text="answer"),
    StopEvent(stop_reason="stop"),
]
_OUTPUT_ONLY_CHAT = [
    StartEvent(id="m", created=0),
    TextEvent(channel="output", text="answer"),
    StopEvent(stop_reason="stop"),
]


class TestCaseOllamaDialect:
    """Cover :class:`OllamaDialect` end-to-end: strategy bindings, the :meth:`render` façade
    dispatch (chat / generate), and the :meth:`assemble` envelope construction (including the
    thinking/output channel routing and error handling).
    """

    @pytest.mark.parametrize(
        ["attr", "expected"],
        [
            pytest.param("PARSER", OllamaParser, id="parser"),
            pytest.param("RENDERER", OllamaRenderer, id="renderer"),
            pytest.param("ASSEMBLER", OllamaAssembler, id="assembler"),
        ],
    )
    def test_bindings(self, attr: str, expected: type) -> None:
        assert getattr(OllamaDialect, attr) is expected

    @pytest.mark.parametrize(
        ["api", "events", "verify"],
        [
            pytest.param("chat", _chat_events(), _verify_chat_render, id="chat"),
            pytest.param("generate", _generate_events(), _verify_generate_render, id="generate"),
        ],
    )
    async def test_render(
        self,
        api: t.Literal["chat", "generate"],
        events: list,
        verify: t.Callable[[list[dict[str, t.Any]]], None],
    ) -> None:
        chunks = [chunk async for chunk in OllamaDialect.render(events, api=api, model="m")]

        verify(chunks)

    @pytest.mark.parametrize(
        ["api", "events", "verify"],
        [
            pytest.param("chat", _chat_events(), _verify_chat_assemble, id="chat"),
            pytest.param("chat", _TEXT_ONLY_CHAT, _verify_chat_assemble_drops_tool_calls, id="chat_drops_tool_calls"),
            pytest.param(
                "chat",
                _NAMED_THINKING_CHAT,
                _make_thinking_verifier("answer", "r1r2"),
                id="chat_named_thinking_concatenated",
            ),
            pytest.param(
                "chat",
                _OTHER_NAMED_CHANNEL_CHAT,
                _make_thinking_verifier("answer", "meta"),
                id="chat_other_named_channel",
            ),
            pytest.param(
                "chat",
                _UNNAMED_CAPTURE_CHAT,
                _make_thinking_verifier("answer", "quiet"),
                id="chat_unnamed_capture_routes_to_thinking",
            ),
            pytest.param(
                "chat",
                _OUTPUT_ONLY_CHAT,
                _make_thinking_verifier("answer", None),
                id="chat_thinking_omitted_when_unused",
            ),
            pytest.param("generate", _generate_events(), _verify_generate_assemble, id="generate"),
        ],
    )
    async def test_assemble(
        self,
        api: t.Literal["chat", "generate"],
        events: list,
        verify: t.Callable[[dict[str, t.Any]], None],
    ) -> None:
        envelope = await OllamaDialect.assemble(events, api=api, model="m")

        verify(envelope)
