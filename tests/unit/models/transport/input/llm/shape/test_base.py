import typing as t

import pytest

from flama.models.transport.input.llm.message import AssistantMessage, TextContent, UserMessage
from flama.models.transport.input.llm.shape import Chat, Conversation, Raw, Shape
from flama.models.transport.input.llm.tool import Tool


class TestCaseShape:
    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(TypeError("abstract"), id="abstract")],
        indirect=["exception"],
    )
    def test_cannot_instantiate_base(self, exception) -> None:
        with exception:
            Shape()  # ty: ignore[call-non-callable]

    @pytest.mark.parametrize(
        ["kwargs", "expected", "exception"],
        [
            pytest.param(
                {"transport": "raw", "prompt": "hi"},
                Raw(fields={"prompt": "hi"}),
                None,
                id="raw",
            ),
            pytest.param(
                {"transport": "chat", "prompt": "hi"},
                Chat(fields={"prompt": "hi"}),
                None,
                id="chat_no_system",
            ),
            pytest.param(
                {"transport": "chat", "prompt": "hi", "system": "be brief"},
                Chat(fields={"prompt": "hi", "system": "be brief"}),
                None,
                id="chat_with_system",
            ),
            pytest.param(
                {
                    "transport": "conversation",
                    "messages": (
                        UserMessage(content=(TextContent(text="hi"),)),
                        AssistantMessage(content=(TextContent(text="hello"),)),
                    ),
                },
                Conversation(
                    fields={
                        "messages": (
                            UserMessage(content=(TextContent(text="hi"),)),
                            AssistantMessage(content=(TextContent(text="hello"),)),
                        )
                    }
                ),
                None,
                id="conversation",
            ),
            pytest.param(
                {"transport": "weird", "prompt": "x"},
                None,
                ValueError("Wrong shape 'weird'"),
                id="unknown_transport",
            ),
            pytest.param(
                {"transport": "raw"},
                None,
                ValueError("'prompt' is required when transport is 'raw'"),
                id="raw_missing_prompt",
            ),
            pytest.param(
                {"transport": "raw", "prompt": "x", "system": "y"},
                None,
                ValueError("'system' is not allowed when transport is 'raw'"),
                id="raw_with_system",
            ),
            pytest.param(
                {
                    "transport": "raw",
                    "prompt": "x",
                    "messages": (UserMessage(content=(TextContent(text="x"),)),),
                },
                None,
                ValueError("'messages' is not allowed when transport is 'raw'"),
                id="raw_with_messages",
            ),
            pytest.param(
                {"transport": "raw", "prompt": "x", "tools": (Tool(name="f"),)},
                None,
                ValueError("'tools' is not allowed when transport is 'raw'"),
                id="raw_with_tools",
            ),
            pytest.param(
                {
                    "transport": "raw",
                    "prompt": "x",
                    "system": "y",
                    "messages": (UserMessage(content=(TextContent(text="x"),)),),
                },
                None,
                ValueError("'system', 'messages' are not allowed when transport is 'raw'"),
                id="raw_with_multiple_rejected_fields",
            ),
            pytest.param(
                {"transport": "chat"},
                None,
                ValueError("'prompt' is required when transport is 'chat'"),
                id="chat_missing_prompt",
            ),
            pytest.param(
                {
                    "transport": "chat",
                    "prompt": "x",
                    "messages": (UserMessage(content=(TextContent(text="x"),)),),
                },
                None,
                ValueError("'messages' is not allowed when transport is 'chat'"),
                id="chat_with_messages",
            ),
            pytest.param(
                {"transport": "conversation"},
                None,
                ValueError("'messages' is required when transport is 'conversation'"),
                id="conversation_missing_messages",
            ),
            pytest.param(
                {"transport": "conversation", "messages": ()},
                None,
                ValueError("'messages' must be non-empty"),
                id="conversation_empty_messages",
            ),
            pytest.param(
                {
                    "transport": "conversation",
                    "messages": (UserMessage(content=(TextContent(text="x"),)),),
                    "prompt": "y",
                },
                None,
                ValueError("'prompt' is not allowed when transport is 'conversation'"),
                id="conversation_with_prompt",
            ),
            pytest.param(
                {
                    "transport": "conversation",
                    "messages": (UserMessage(content=(TextContent(text="x"),)),),
                    "system": "y",
                },
                None,
                ValueError("'system' is not allowed when transport is 'conversation'"),
                id="conversation_with_system",
            ),
            pytest.param(
                {
                    "transport": "conversation",
                    "messages": (UserMessage(content=(TextContent(text="x"),)),),
                    "prompt": "y",
                    "system": "z",
                },
                None,
                ValueError("'prompt', 'system' are not allowed when transport is 'conversation'"),
                id="conversation_with_multiple_rejected_fields",
            ),
        ],
        indirect=["exception"],
    )
    def test_build(self, kwargs: dict[str, t.Any], expected: Shape | None, exception) -> None:
        with exception:
            assert Shape.build(kwargs.pop("transport"), **kwargs) == expected
