import typing as t

import pytest

from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    Content,
    ImageURI,
    ImageURL,
    Message,
    SourceURI,
    SourceURL,
    SystemMessage,
    TextContent,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from flama.models.transport.input.llm.tool import Tool
from flama.models.wire.dialect.llm.anthropic.parser import AnthropicParser


class TestCaseAnthropicParser:
    """Cover :class:`AnthropicParser`'s wire-translation surface end-to-end.

    Anthropic's wire shape carries images under a ``source: {type: base64|url, ...}`` envelope and uses a
    fixed ``image/png|jpeg|gif|webp`` media-type vocabulary. ``tool_use`` / ``tool_result`` / ``thinking`` /
    ``redacted_thinking`` blocks are split off by :meth:`_parse_messages` before they reach
    :meth:`_parse_part`; seeing one at the part level is a structural error surfaced as
    :class:`LLMUnsupportedContentPart`. The :meth:`_parse_messages` override flattens the optional
    top-level ``system`` payload and expands user / assistant turns into Flama's canonical L2 shape.
    The :meth:`_parse_tool` override consumes Anthropic's flat ``{name, description, input_schema}``
    shape (no OpenAI-style ``function:`` envelope).
    """

    @pytest.mark.parametrize(
        ["part", "expected", "exception"],
        [
            pytest.param(
                {"type": "text", "text": "hi"},
                TextContent(text="hi"),
                None,
                id="text",
            ),
            pytest.param(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": "xxx"},
                },
                ImageURI(source=SourceURI.parse("xxx"), format="png"),
                None,
                id="image_base64_png",
            ),
            pytest.param(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": "yyy"},
                },
                ImageURI(source=SourceURI.parse("yyy"), format="jpeg"),
                None,
                id="image_base64_jpeg",
            ),
            pytest.param(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "IMAGE/WEBP", "data": "zzz"},
                },
                ImageURI(source=SourceURI.parse("zzz"), format="webp"),
                None,
                id="image_base64_media_type_case_insensitive",
            ),
            pytest.param(
                {
                    "type": "image",
                    "source": {"type": "url", "url": "https://example.com/cat.png"},
                },
                ImageURL(source=SourceURL.parse("https://example.com/cat.png")),
                None,
                id="image_url",
            ),
            pytest.param(
                "not-a-dict",
                None,
                ValueError("content parts must be objects with a 'type' field"),
                id="not_a_dict",
            ),
            pytest.param(
                {},
                None,
                ValueError("content parts must be objects with a 'type' field"),
                id="missing_type",
            ),
            pytest.param(
                {"type": "text"},
                None,
                ValueError("text content parts must carry a string 'text' field"),
                id="text_missing_text",
            ),
            pytest.param(
                {"type": "image"},
                None,
                ValueError("'image' content parts must carry a 'source' object with a 'type' field"),
                id="image_missing_source",
            ),
            pytest.param(
                {"type": "image", "source": "not-an-object"},
                None,
                ValueError("'image' content parts must carry a 'source' object with a 'type' field"),
                id="image_source_not_object",
            ),
            pytest.param(
                {"type": "image", "source": {"type": "base64", "media_type": "image/png"}},
                None,
                ValueError("'image' base64 sources must carry a 'data' string and a 'media_type' string"),
                id="image_base64_missing_data",
            ),
            pytest.param(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/svg+xml", "data": "x"},
                },
                None,
                ValueError("Wrong image media_type 'image/svg+xml'"),
                id="image_base64_unsupported_media_type",
            ),
            pytest.param(
                {"type": "image", "source": {"type": "url"}},
                None,
                ValueError("'image' url sources must carry a 'url' string"),
                id="image_url_missing_url",
            ),
            pytest.param(
                {"type": "image", "source": {"type": "ftp"}},
                None,
                ValueError("Wrong image source type 'ftp', expected one of: ['base64', 'url']"),
                id="image_unsupported_source_type",
            ),
            pytest.param(
                {"type": "tool_use", "id": "x", "name": "n", "input": {}},
                None,
                LLMUnsupportedContentPart,
                id="tool_use_rejected_at_part_level",
            ),
            pytest.param(
                {"type": "tool_result", "tool_use_id": "x", "content": "ok"},
                None,
                LLMUnsupportedContentPart,
                id="tool_result_rejected_at_part_level",
            ),
            pytest.param(
                {"type": "thinking", "thinking": "..."},
                None,
                LLMUnsupportedContentPart,
                id="thinking_rejected_at_part_level",
            ),
            pytest.param(
                {"type": "redacted_thinking", "data": "..."},
                None,
                LLMUnsupportedContentPart,
                id="redacted_thinking_rejected_at_part_level",
            ),
            pytest.param(
                {"type": "video", "source": {"type": "url", "url": "https://x"}},
                None,
                LLMUnsupportedContentPart,
                id="unsupported_kind",
            ),
        ],
        indirect=["exception"],
    )
    def test__parse_part(self, part: t.Any, expected: Content | None, exception) -> None:
        with exception:
            assert AnthropicParser._parse_part(part) == expected

    @pytest.mark.parametrize(
        ["values", "system", "expected", "exception"],
        [
            pytest.param([], None, (), None, id="empty"),
            pytest.param(
                [{"role": "user", "content": "hi"}],
                None,
                (UserMessage(content=(TextContent(text="hi"),)),),
                None,
                id="canonical_user",
            ),
            pytest.param(
                [{"role": "user", "content": "hi"}],
                "be brief",
                (
                    SystemMessage(content=(TextContent(text="be brief"),)),
                    UserMessage(content=(TextContent(text="hi"),)),
                ),
                None,
                id="system_as_string",
            ),
            pytest.param(
                [{"role": "user", "content": "hi"}],
                [{"type": "text", "text": "be "}, {"type": "text", "text": "brief"}],
                (
                    SystemMessage(content=(TextContent(text="be brief"),)),
                    UserMessage(content=(TextContent(text="hi"),)),
                ),
                None,
                id="system_as_list",
            ),
            pytest.param(
                [{"role": "user", "content": "hi"}],
                [{"type": "image"}],
                (UserMessage(content=(TextContent(text="hi"),)),),
                None,
                id="system_unsupported_block_dropped",
            ),
            pytest.param(
                [{"role": "user", "content": "hi"}],
                42,
                (UserMessage(content=(TextContent(text="hi"),)),),
                None,
                id="system_unsupported_type_dropped",
            ),
            pytest.param(
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "tool_result", "tool_use_id": "c1", "content": "ok"},
                            {"type": "tool_result", "tool_use_id": "c2", "content": "fail"},
                        ],
                    },
                ],
                None,
                (
                    ToolMessage(content=(TextContent(text="ok"),), tool_call_id="c1"),
                    ToolMessage(content=(TextContent(text="fail"),), tool_call_id="c2"),
                ),
                None,
                id="multi_tool_result_user_turn",
            ),
            pytest.param(
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "tool_result", "tool_use_id": "c1", "content": "ok"},
                            {"type": "text", "text": "thanks"},
                        ],
                    },
                ],
                None,
                (
                    ToolMessage(content=(TextContent(text="ok"),), tool_call_id="c1"),
                    UserMessage(content=(TextContent(text="thanks"),)),
                ),
                None,
                id="tool_result_with_residual_user_text",
            ),
            pytest.param(
                [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "let me think..."},
                            {"type": "text", "text": "answer"},
                        ],
                    },
                ],
                None,
                (
                    AssistantMessage(
                        content=(TextContent(text="answer"),),
                        reasoning_content="let me think...",
                    ),
                ),
                None,
                id="assistant_with_thinking",
            ),
            pytest.param(
                [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "id": "c1", "name": "lookup", "input": {"q": "x"}},
                        ],
                    },
                ],
                None,
                (
                    AssistantMessage(
                        content=None,
                        tool_calls=(
                            ToolCall(
                                id="c1",
                                function={"name": "lookup", "arguments": '{"q": "x"}'},
                            ),
                        ),
                    ),
                ),
                None,
                id="assistant_with_tool_use",
            ),
            pytest.param(
                [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "redacted_thinking", "data": "..."},
                            {"type": "text", "text": "answer"},
                        ],
                    },
                ],
                None,
                (AssistantMessage(content=(TextContent(text="answer"),)),),
                None,
                id="redacted_thinking_dropped",
            ),
            pytest.param(
                [{"role": "user", "content": []}],
                None,
                (),
                None,
                id="empty_user_content_dropped",
            ),
            pytest.param(
                ["not-a-dict"],
                None,
                None,
                ValueError("messages element must be an object"),
                id="non_dict_message",
            ),
            pytest.param(
                [{"role": "system", "content": "be brief"}],
                None,
                None,
                ValueError("Wrong role 'system', expected one of: ['user', 'assistant']"),
                id="invalid_role",
            ),
            pytest.param(
                [{"role": "user", "content": 42}],
                None,
                None,
                ValueError("user 'content' must be a string or a list of content blocks"),
                id="user_content_invalid_type",
            ),
            pytest.param(
                [{"role": "user", "content": ["not-a-dict"]}],
                None,
                None,
                ValueError("user content blocks must be objects with a 'type' field"),
                id="user_content_block_invalid",
            ),
            pytest.param(
                [{"role": "user", "content": [{"type": "tool_result"}]}],
                None,
                None,
                ValueError("'tool_result' blocks must carry a 'tool_use_id' string"),
                id="tool_result_missing_id",
            ),
            pytest.param(
                [{"role": "assistant", "content": 42}],
                None,
                None,
                ValueError("assistant 'content' must be a string or a list of content blocks"),
                id="assistant_content_invalid_type",
            ),
            pytest.param(
                [{"role": "assistant", "content": ["not-a-dict"]}],
                None,
                None,
                ValueError("assistant content blocks must be objects with a 'type' field"),
                id="assistant_content_block_invalid",
            ),
            pytest.param(
                [{"role": "assistant", "content": [{"type": "ghost"}]}],
                None,
                None,
                ValueError("Wrong assistant content block 'ghost'"),
                id="assistant_unknown_block",
            ),
        ],
        indirect=["exception"],
    )
    def test__parse_messages(
        self,
        values: list[dict[str, t.Any]],
        system: t.Any,
        expected: tuple[Message, ...] | None,
        exception,
    ) -> None:
        with exception:
            assert AnthropicParser._parse_messages(values, system=system) == expected

    @pytest.mark.parametrize(
        ["value", "expected", "exception"],
        [
            pytest.param(
                {"name": "lookup", "description": "d", "input_schema": {"x": 1}},
                Tool(name="lookup", description="d", parameters={"x": 1}),
                None,
                id="full",
            ),
            pytest.param(
                {"name": "lookup"},
                Tool(name="lookup"),
                None,
                id="minimal",
            ),
            pytest.param(
                "not-a-dict",
                None,
                ValueError("tools element must be an object"),
                id="not_a_dict",
            ),
            pytest.param(
                {},
                None,
                ValueError("'name' must be a non-empty string"),
                id="missing_name",
            ),
            pytest.param(
                {"name": ""},
                None,
                ValueError("'name' must be a non-empty string"),
                id="empty_name",
            ),
        ],
        indirect=["exception"],
    )
    def test__parse_tool(self, value: t.Any, expected: Tool | None, exception) -> None:
        with exception:
            assert AnthropicParser._parse_tool(value) == expected

    @pytest.mark.parametrize(
        ["value", "expected"],
        [
            pytest.param("plain", "plain", id="string"),
            pytest.param(
                [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}], "ab", id="list_of_text_blocks"
            ),
            pytest.param(
                [{"type": "image", "source": {"type": "url", "url": "https://x"}}],
                '{"type": "image", "source": {"type": "url", "url": "https://x"}}',
                id="list_with_non_text_block_json_encoded",
            ),
            pytest.param(
                [{"type": "text", "text": "a"}, {"type": "image", "url": "u"}],
                'a{"type": "image", "url": "u"}',
                id="list_mixed_text_and_non_text",
            ),
            pytest.param([42, "not-a-dict"], "", id="list_of_non_dicts_dropped"),
            pytest.param(None, "", id="none"),
            pytest.param({"k": "v"}, '{"k": "v"}', id="non_string_non_list_json_encoded"),
            pytest.param(123, "123", id="scalar_json_encoded"),
        ],
    )
    def test__tool_result_text(self, value: t.Any, expected: str) -> None:
        assert AnthropicParser._tool_result_text(value) == expected
