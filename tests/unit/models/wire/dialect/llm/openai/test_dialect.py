import json
import typing as t
import uuid

import pytest

from flama.http.responses.sse import ServerSentEvent
from flama.models.exceptions import LLMGenerationError
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect.llm.openai import OpenAIAssembler, OpenAIDialect, OpenAIParser, OpenAIRenderer

_GEN_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def _chat_events() -> list:
    return [
        StartEvent(id="msg-1", created=1000, input_tokens=4),
        TextEvent(channel="output", text="Hello"),
        ToolEvent(id="call-1", name="lookup", arguments={"q": "x"}),
        StopEvent(stop_reason="stop", output_tokens=8),
    ]


def _completion_events() -> list:
    return [
        StartEvent(id="msg-1", created=2000, input_tokens=3),
        TextEvent(channel="output", text="World"),
        StopEvent(stop_reason="stop", output_tokens=5),
    ]


def _response_events() -> list:
    return [
        StartEvent(id="msg-1", created=3000, input_tokens=6),
        TextEvent(channel="thinking", text="reasoning..."),
        TextEvent(channel="output", text="answer"),
        StopEvent(stop_reason="stop", output_tokens=9),
    ]


def _error_events() -> list:
    return [
        StartEvent(id="msg-1", created=1000),
        StopEvent(stop_reason="error"),
    ]


def _verify_chat_render(frames: list[ServerSentEvent]) -> None:
    assert all(isinstance(frame, ServerSentEvent) for frame in frames)
    bodies = [json.loads(frame.data) for frame in frames if frame.data != "[DONE]"]
    first = bodies[0]
    assert first["object"] == "chat.completion.chunk"
    assert first["id"].startswith("chatcmpl-")
    assert _GEN_ID.hex in first["id"]
    assert first["choices"][0]["delta"] == {"role": "assistant"}
    assert any(b["choices"][0].get("finish_reason") == "stop" for b in bodies)
    assert frames[-1].data == "[DONE]"


def _verify_completion_render(frames: list[ServerSentEvent]) -> None:
    bodies = [json.loads(frame.data) for frame in frames if frame.data != "[DONE]"]
    assert all(b["object"] == "text_completion" for b in bodies)
    assert all(b["id"].startswith("cmpl-") for b in bodies)
    assert any(b["choices"][0].get("text") == "World" for b in bodies)
    assert frames[-1].data == "[DONE]"


def _verify_response_render(frames: list[ServerSentEvent]) -> None:
    events = [frame.event for frame in frames]
    assert events[0] == "response.created"
    assert "response.completed" in events
    assert any(e == "response.output_text.delta" for e in events)


def _verify_chat_assemble(envelope: dict[str, t.Any]) -> None:
    assert envelope["object"] == "chat.completion"
    assert envelope["model"] == "m"
    assert envelope["created"] == 1000
    assert envelope["id"].startswith("chatcmpl-")
    assert _GEN_ID.hex in envelope["id"]
    assert envelope["choices"][0]["finish_reason"] == "stop"
    assert envelope["choices"][0]["message"]["content"] == "Hello"
    tool_calls = envelope["choices"][0]["message"]["tool_calls"]
    assert tool_calls[0]["function"]["name"] == "lookup"
    assert json.loads(tool_calls[0]["function"]["arguments"]) == {"q": "x"}
    assert envelope["usage"] == {"prompt_tokens": 4, "completion_tokens": 8, "total_tokens": 12}


def _verify_completion_assemble(envelope: dict[str, t.Any]) -> None:
    assert envelope["object"] == "text_completion"
    assert envelope["id"].startswith("cmpl-")
    assert envelope["choices"][0]["text"] == "World"
    assert envelope["choices"][0]["finish_reason"] == "stop"
    assert envelope["usage"] == {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8}


def _verify_response_assemble(envelope: dict[str, t.Any]) -> None:
    assert envelope["object"] == "response"
    assert envelope["id"].startswith("resp-")
    assert envelope["status"] == "completed"
    kinds = [item["type"] for item in envelope["output"]]
    assert "reasoning" in kinds
    assert "message" in kinds
    message = next(item for item in envelope["output"] if item["type"] == "message")
    assert message["content"][0]["text"] == "answer"
    assert envelope["usage"] == {"input_tokens": 6, "output_tokens": 9, "total_tokens": 15}


class TestCaseOpenAIDialect:
    """Cover :class:`OpenAIDialect` end-to-end: strategy bindings, the :meth:`render` façade
    dispatch (chat / completion / response), and the :meth:`assemble` envelope construction.
    """

    @pytest.mark.parametrize(
        ["attr", "expected"],
        [
            pytest.param("PARSER", OpenAIParser, id="parser"),
            pytest.param("RENDERER", OpenAIRenderer, id="renderer"),
            pytest.param("ASSEMBLER", OpenAIAssembler, id="assembler"),
        ],
    )
    def test_bindings(self, attr: str, expected: type) -> None:
        assert getattr(OpenAIDialect, attr) is expected

    @pytest.mark.parametrize(
        ["api", "events", "verify"],
        [
            pytest.param("chat", _chat_events(), _verify_chat_render, id="chat"),
            pytest.param("completion", _completion_events(), _verify_completion_render, id="completion"),
            pytest.param("response", _response_events(), _verify_response_render, id="response"),
        ],
    )
    async def test_render(
        self,
        api: t.Literal["chat", "completion", "response"],
        events: list,
        verify: t.Callable[[list[ServerSentEvent]], None],
    ) -> None:
        frames = [
            frame async for frame in OpenAIDialect.render(events, api=api, model="m", generation_id=_GEN_ID)
        ]

        verify(frames)

    @pytest.mark.parametrize(
        ["api", "events", "verify"],
        [
            pytest.param("chat", _chat_events(), _verify_chat_assemble, id="chat"),
            pytest.param("completion", _completion_events(), _verify_completion_assemble, id="completion"),
            pytest.param("response", _response_events(), _verify_response_assemble, id="response"),
        ],
    )
    async def test_assemble(
        self,
        api: t.Literal["chat", "completion", "response"],
        events: list,
        verify: t.Callable[[dict[str, t.Any]], None],
    ) -> None:
        envelope = await OpenAIDialect.assemble(events, api=api, model="m", generation_id=_GEN_ID)

        verify(envelope)

    @pytest.mark.parametrize(
        "api",
        [
            pytest.param("chat", id="chat"),
            pytest.param("completion", id="completion"),
            pytest.param("response", id="response"),
        ],
    )
    async def test_assemble_raises_llm_generation_error(
        self, api: t.Literal["chat", "completion", "response"]
    ) -> None:
        with pytest.raises(LLMGenerationError, match="LLM stream generation failed"):
            await OpenAIDialect.assemble(_error_events(), api=api, model="m", generation_id=_GEN_ID)
