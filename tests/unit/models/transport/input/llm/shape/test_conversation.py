import base64
import io

import pytest
from PIL import Image

from flama.models.exceptions import LLMUnsupportedCapability
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    ImageURI,
    Message,
    SourceURI,
    TextContent,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from flama.models.transport.input.llm.shape import Conversation
from flama.models.transport.input.llm.shape._base import Shape  # noqa
from flama.models.transport.input.llm.tool import Tool
from tests.unit.models.transport.input.llm.shape.conftest import FakeBackend, FakeMultimodalBackend


def _png_data_uri() -> str:
    img = Image.new("RGB", (1, 1), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _user(text: str) -> Message:
    return UserMessage(content=(TextContent(text=text),))


def _assistant(text: str) -> Message:
    return AssistantMessage(content=(TextContent(text=text),))


class TestCaseConversation:
    def test_init(self) -> None:
        msgs = (_user("hi"), _assistant("hello"))

        t_ = Conversation(fields={"messages": msgs})

        assert t_.transport == "conversation"
        assert t_.messages == msgs

    async def test_render(self, backend: FakeBackend) -> None:
        messages = (_user("a"), _assistant("b"))

        await Conversation(fields={"messages": messages}).render(backend)

        assert backend.template_calls == [[{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]]
        assert backend.encode_calls == []

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(ValueError("Model has no chat template"), id="no_chat_template")],
        indirect=["exception"],
    )
    async def test_render_raises_without_chat_template(self, backend_no_template: FakeBackend, exception) -> None:
        with exception:
            await Conversation(fields={"messages": (_user("hi"),)}).render(backend_no_template)

    async def test_render_forwards_chat_template_kwargs(self, backend: FakeBackend) -> None:
        await Conversation(fields={"messages": (_user("hi"),)}).render(
            backend, chat_template_kwargs={"enable_thinking": False}
        )

        assert backend.template_kwargs == [{"enable_thinking": False}]

    async def test_render_forwards_tools_to_template(self, backend: FakeBackend) -> None:
        tool = Tool(name="f", parameters={})

        await Conversation(fields={"messages": (_user("hi"),), "tools": (tool,)}).render(backend)

        assert backend.template_kwargs == [
            {"tools": [{"type": "function", "function": {"name": "f", "parameters": {}}}]}
        ]

    async def test_render_serialises_assistant_tool_calls(self, backend: FakeBackend) -> None:
        call = ToolCall(id="c1", function={"name": "f", "arguments": "{}"})

        await Conversation(
            fields={
                "messages": (
                    _user("hi"),
                    AssistantMessage(tool_calls=(call,)),
                    ToolMessage(tool_call_id="c1", content=(TextContent(text="42"),)),
                )
            }
        ).render(backend)

        assert backend.template_calls == [
            [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}}],
                },
                {"role": "tool", "content": "42", "tool_call_id": "c1"},
            ]
        ]

    async def test_render_rejects_multimodal_on_text_only_backend(self, backend: FakeBackend) -> None:
        multimodal = (
            UserMessage(
                content=(TextContent(text="describe"), ImageURI(source=SourceURI(data="X"), format="png")),
            ),
        )

        with pytest.raises(LLMUnsupportedCapability, match="does not support image"):
            await Conversation(fields={"messages": multimodal}).render(backend)

    async def test_render_passes_multimodal_through_capable_backend(
        self, multimodal_backend: FakeMultimodalBackend
    ) -> None:
        url = _png_data_uri()
        multimodal = (
            UserMessage(
                content=(
                    TextContent(text="describe"),
                    ImageURI(source=SourceURI.parse(url), format="png"),
                ),
            ),
        )

        inputs = await Conversation(fields={"messages": multimodal}).render(multimodal_backend)

        assert multimodal_backend.template_calls == [
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image"},
                    ],
                }
            ]
        ]
        assert len(inputs.images) == 1
        assert inputs.audios == ()
