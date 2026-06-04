import typing as t

import pytest

from flama.models.exceptions import LLMGenerationError
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    Content,
    Message,
    SystemMessage,
    TextContent,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from flama.models.transport.input.llm.tool import Tool
from flama.models.transport.output.llm.event import (
    Event,
    StartEvent,
    StopEvent,
    TextEvent,
    ToolEvent,
)
from flama.models.wire.dialect.base import (
    Assembler,
    CoalescingRenderer,
    Dialect,
    Parser,
    Renderer,
)


class _SilentParser(Parser):
    """Concrete :class:`Parser` subclass exposing the dialect-shared parsing surface to tests.

    Implements :meth:`_parse_part` against a minimal text-only dialect so :meth:`_parse_message` can be exercised
    end-to-end; tests that target the shared ``_parse_tool`` / ``_parse_tool_call`` envelope use the inherited
    behaviour unchanged.
    """

    @classmethod
    def _parse_part(cls, part: t.Any) -> Content:
        if not isinstance(part, dict) or part.get("type") != "text":
            raise ValueError("only text parts supported")
        text = part.get("text")
        if not isinstance(text, str):
            raise ValueError("text content parts must carry a string 'text' field")
        return TextContent(text=text)


class _SilentRenderer(Renderer[Event]):
    """Concrete :class:`Renderer` for tests; passes events through verbatim."""

    def on_text(self, block: TextEvent) -> t.Iterable[Event]:
        yield block

    def on_tool(self, block: ToolEvent) -> t.Iterable[Event]:
        yield block

    def on_stop(self, block: StopEvent) -> t.Iterable[Event]:
        return ()


class _SilentAssembler(Assembler):
    """Concrete :class:`Assembler` for tests; emits a minimal envelope echoing the captured events."""

    @classmethod
    def envelope(
        cls,
        events: tuple[Event, ...],
        /,
        *,
        start: StartEvent,
        stop: StopEvent,
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        return {"events": list(events), "start": start, "stop": stop, "kwargs": kwargs}


class _SilentDialect(Dialect):
    """Concrete :class:`Dialect` subclass binding :class:`_SilentParser` / :class:`_SilentRenderer` /
    :class:`_SilentAssembler` for façade-dispatch tests."""

    PARSER = _SilentParser
    RENDERER = _SilentRenderer
    ASSEMBLER = _SilentAssembler


class TestCaseParser:
    """Cover :class:`Parser`'s shared translation surface — the :meth:`parse` dispatcher, the
    :meth:`_parse_messages` default, the :meth:`_parse_message` template-method, the OpenAI-flavoured
    :meth:`_parse_tool` / :meth:`_parse_tool_call` envelope, and the :meth:`_format_from_data_uri`
    helper. All of these live on :class:`Parser` and are reused unchanged by every concrete subclass
    because the OpenAI-style envelope is universal across the dialects Flama speaks today.
    """

    @pytest.mark.parametrize(
        ["value", "kind", "system", "expected", "exception"],
        [
            pytest.param(
                [{"role": "user", "content": "hi"}],
                "messages",
                None,
                (UserMessage(content=(TextContent(text="hi"),)),),
                None,
                id="messages_kind",
            ),
            pytest.param(
                [{"type": "function", "function": {"name": "lookup"}}],
                "tools",
                None,
                (Tool(name="lookup"),),
                None,
                id="tools_kind",
            ),
            pytest.param(
                [],
                "messages",
                None,
                (),
                None,
                id="messages_empty",
            ),
            pytest.param(
                [],
                "tools",
                None,
                (),
                None,
                id="tools_empty",
            ),
            pytest.param(
                [{"role": "user", "content": "hi"}],
                "messages",
                "be brief",
                None,
                ValueError("_SilentParser does not accept a top-level 'system' field"),
                id="messages_system_rejected_by_default",
            ),
            pytest.param(
                [{"content": "no role"}],
                "messages",
                None,
                None,
                ValueError("Wrong message, expected an object with at least a 'role' field"),
                id="messages_propagates_value_error",
            ),
            pytest.param(
                ["not a dict"],
                "tools",
                None,
                None,
                ValueError("tools element must be an object"),
                id="tools_propagates_value_error",
            ),
            pytest.param(
                [],
                "unknown",
                None,
                None,
                ValueError("Wrong kind 'unknown', expected one of: ['messages', 'tools']"),
                id="unknown_kind",
            ),
        ],
        indirect=["exception"],
    )
    def test_parse(
        self,
        value: t.Any,
        kind: t.Any,
        system: t.Any,
        expected: tuple[t.Any, ...] | None,
        exception,
    ) -> None:
        with exception:
            assert _SilentParser.parse(value, kind=kind, system=system) == expected

    @pytest.mark.parametrize(
        ["values", "system", "expected", "exception"],
        [
            pytest.param([], None, (), None, id="empty"),
            pytest.param(
                [{"role": "user", "content": "hi"}],
                None,
                (UserMessage(content=(TextContent(text="hi"),)),),
                None,
                id="single",
            ),
            pytest.param(
                [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
                None,
                (
                    UserMessage(content=(TextContent(text="a"),)),
                    AssistantMessage(content=(TextContent(text="b"),)),
                ),
                None,
                id="multi",
            ),
            pytest.param(
                [],
                "be brief",
                None,
                ValueError("_SilentParser does not accept a top-level 'system' field"),
                id="system_rejected",
            ),
            pytest.param(
                [{"content": "no role"}],
                None,
                None,
                ValueError("Wrong message, expected an object with at least a 'role' field"),
                id="propagates_value_error",
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
            assert _SilentParser._parse_messages(values, system=system) == expected

    @pytest.mark.parametrize(
        ["values", "expected", "exception"],
        [
            pytest.param([], (), None, id="empty"),
            pytest.param(
                [{"type": "function", "function": {"name": "lookup"}}],
                (Tool(name="lookup"),),
                None,
                id="single",
            ),
            pytest.param(
                [
                    {"type": "function", "function": {"name": "a"}},
                    {"type": "function", "function": {"name": "b"}},
                ],
                (Tool(name="a"), Tool(name="b")),
                None,
                id="multi",
            ),
            pytest.param(
                ["not a dict"],
                None,
                ValueError("tools element must be an object"),
                id="propagates_value_error",
            ),
        ],
        indirect=["exception"],
    )
    def test__parse_tools(
        self,
        values: list[t.Any],
        expected: tuple[Tool, ...] | None,
        exception,
    ) -> None:
        with exception:
            assert _SilentParser._parse_tools(values) == expected

    @pytest.mark.parametrize(
        ["value", "expected", "exception"],
        [
            pytest.param(
                {"type": "function", "function": {"name": "lookup", "description": "d", "parameters": {"x": 1}}},
                Tool(name="lookup", description="d", parameters={"x": 1}),
                None,
                id="full_envelope",
            ),
            pytest.param(
                {"type": "function", "function": {"name": "lookup"}},
                Tool(name="lookup"),
                None,
                id="minimal_envelope",
            ),
            pytest.param(
                {"function": {"name": "lookup"}},
                Tool(name="lookup"),
                None,
                id="implicit_function_type",
            ),
            pytest.param(
                "not a dict",
                None,
                ValueError("tools element must be an object"),
                id="not_a_dict",
            ),
            pytest.param(
                {"type": "code_interpreter", "function": {"name": "x"}},
                None,
                ValueError("Wrong tool type 'code_interpreter', expected 'function'"),
                id="unsupported_type",
            ),
            pytest.param(
                {"type": "function"},
                None,
                ValueError("tools element must carry a 'function' object"),
                id="missing_function",
            ),
            pytest.param(
                {"type": "function", "function": {}},
                None,
                ValueError("'name' must be a non-empty string"),
                id="missing_name",
            ),
            pytest.param(
                {"type": "function", "function": {"name": ""}},
                None,
                ValueError("'name' must be a non-empty string"),
                id="empty_name",
            ),
            pytest.param(
                {"type": "function", "function": {"name": "lookup", "description": 42}},
                None,
                ValueError("'description' must be a string when set"),
                id="non_string_description",
            ),
            pytest.param(
                {"type": "function", "function": {"name": "lookup", "parameters": "x"}},
                None,
                ValueError("'parameters' must be an object"),
                id="non_object_parameters",
            ),
        ],
        indirect=["exception"],
    )
    def test__parse_tool(self, value: t.Any, expected: Tool | None, exception) -> None:
        with exception:
            assert _SilentParser._parse_tool(value) == expected

    @pytest.mark.parametrize(
        ["value", "expected", "exception"],
        [
            pytest.param(
                {"id": "call_1", "function": {"name": "lookup", "arguments": "{}"}},
                ToolCall(id="call_1", function={"name": "lookup", "arguments": "{}"}),
                None,
                id="with_id",
            ),
            pytest.param(
                {"function": {"name": "lookup", "arguments": "{}"}},
                ToolCall(id=None, function={"name": "lookup", "arguments": "{}"}),
                None,
                id="without_id",
            ),
            pytest.param(
                "not-a-dict",
                None,
                ValueError("tool_calls element must be an object"),
                id="not_a_dict",
            ),
            pytest.param(
                {"id": "call_1"},
                None,
                ValueError("tool_calls element must carry a 'function' object"),
                id="missing_function",
            ),
            pytest.param(
                {"id": 42, "function": {"name": "lookup"}},
                None,
                ValueError("'id' must be a string when set"),
                id="non_string_id",
            ),
        ],
        indirect=["exception"],
    )
    def test__parse_tool_call(self, value: t.Any, expected: ToolCall | None, exception) -> None:
        with exception:
            assert _SilentParser._parse_tool_call(value) == expected

    @pytest.mark.parametrize(
        ["value", "expected", "exception"],
        [
            pytest.param(
                {"role": "user", "content": "hi"},
                UserMessage(content=(TextContent(text="hi"),)),
                None,
                id="string_content_user",
            ),
            pytest.param(
                {"role": "system", "content": "be brief"},
                SystemMessage(content=(TextContent(text="be brief"),)),
                None,
                id="string_content_system",
            ),
            pytest.param(
                {"role": "assistant", "content": "ok"},
                AssistantMessage(content=(TextContent(text="ok"),)),
                None,
                id="assistant_with_content",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}],
                },
                UserMessage(content=(TextContent(text="a"), TextContent(text="b"))),
                None,
                id="structured_content_user",
            ),
            pytest.param(
                {"role": "tool", "content": "ok", "tool_call_id": "call_1"},
                ToolMessage(content=(TextContent(text="ok"),), tool_call_id="call_1"),
                None,
                id="tool_message_with_call_id",
            ),
            pytest.param(
                {
                    "role": "assistant",
                    "content": "ok",
                    "reasoning_content": "thinking…",
                },
                AssistantMessage(content=(TextContent(text="ok"),), reasoning_content="thinking…"),
                None,
                id="assistant_with_reasoning_content",
            ),
            pytest.param(
                "not a dict",
                None,
                ValueError("Wrong message, expected an object with at least a 'role' field"),
                id="not_a_dict",
            ),
            pytest.param(
                {"content": "no role"},
                None,
                ValueError("Wrong message, expected an object with at least a 'role' field"),
                id="missing_role",
            ),
            pytest.param(
                {"role": "user", "content": 7},
                None,
                ValueError("'content' must be a string or a list of content parts"),
                id="invalid_content_type",
            ),
            pytest.param(
                {"role": "assistant", "tool_calls": "not a list"},
                None,
                ValueError("'tool_calls' must be a list of objects"),
                id="non_list_tool_calls",
            ),
            pytest.param(
                {"role": "system"},
                None,
                ValueError("'content' is required for 'system' messages"),
                id="system_without_content",
            ),
            pytest.param(
                {"role": "user"},
                None,
                ValueError("'content' is required for 'user' messages"),
                id="user_without_content",
            ),
            pytest.param(
                {"role": "tool", "tool_call_id": "c1"},
                None,
                ValueError("'content' is required for 'tool' messages"),
                id="tool_without_content",
            ),
            pytest.param(
                {"role": "tool", "content": "ok"},
                None,
                ValueError("'tool_call_id' is required for 'tool' messages"),
                id="tool_without_id",
            ),
            pytest.param(
                {"role": "ghost", "content": "x"},
                None,
                ValueError("Wrong role 'ghost'"),
                id="invalid_role",
            ),
            pytest.param(
                {"role": "assistant"},
                None,
                ValueError("'content' or 'tool_calls' is required for 'assistant' messages"),
                id="assistant_without_content_or_tool_calls",
            ),
        ],
        indirect=["exception"],
    )
    def test__parse_message(self, value: t.Any, expected: Message | None, exception) -> None:
        with exception:
            assert _SilentParser._parse_message(value) == expected

    @pytest.mark.parametrize(
        ["url", "allowed", "default", "expected"],
        [
            pytest.param("data:image/png;base64,xxx", ("png", "jpeg"), "png", "png", id="known_format"),
            pytest.param("data:image/jpeg;base64,xxx", ("png", "jpeg"), "png", "jpeg", id="known_alt_format"),
            pytest.param("data:image/svg;base64,xxx", ("png",), "png", "png", id="unknown_falls_back_default"),
            pytest.param("data:;base64,xxx", ("png",), "png", "png", id="missing_media_type"),
            pytest.param("data:application/pdf,...", ("png",), "png", "png", id="non_image_media_default"),
        ],
    )
    def test_format_from_data_uri(self, url: str, allowed: tuple[str, ...], default: str, expected: str) -> None:
        assert _SilentParser._format_from_data_uri(url, allowed=allowed, default=default) == expected


class TestCaseDialect:
    """Cover :class:`Dialect`'s strategy-binding surface end-to-end: the abstract ``PARSER`` /
    ``RENDERER`` / ``ASSEMBLER`` slots that concrete dialects must bind, and the concrete
    :meth:`parse` / :meth:`render` / :meth:`assemble` relays that dispatch to the bound strategies.

    The :meth:`parse` façade is a thin relay to the bound :attr:`PARSER`; the dialect surface
    mirrors :meth:`render` / :meth:`assemble` so callers always reach parsing through
    ``Dialect.parse(value, kind=...)``.
    """

    @pytest.mark.parametrize(
        ["value", "kind", "system", "expected", "exception"],
        [
            pytest.param(
                [{"role": "user", "content": "hi"}],
                "messages",
                None,
                (UserMessage(content=(TextContent(text="hi"),)),),
                None,
                id="messages_kind",
            ),
            pytest.param(
                [{"type": "function", "function": {"name": "lookup"}}],
                "tools",
                None,
                (Tool(name="lookup"),),
                None,
                id="tools_kind",
            ),
            pytest.param(
                [{"content": "no role"}],
                "messages",
                None,
                None,
                ValueError("Wrong message, expected an object with at least a 'role' field"),
                id="messages_propagates_value_error",
            ),
            pytest.param(
                ["not a dict"],
                "tools",
                None,
                None,
                ValueError("tools element must be an object"),
                id="tools_propagates_value_error",
            ),
        ],
        indirect=["exception"],
    )
    def test_parse(
        self,
        value: t.Any,
        kind: t.Any,
        system: t.Any,
        expected: tuple[t.Any, ...] | None,
        exception,
    ) -> None:
        with exception:
            assert _SilentDialect.parse(value, kind=kind, system=system) == expected

    def test_subclass_must_bind_parser(self) -> None:
        """A concrete dialect that omits :attr:`PARSER` raises ``AttributeError`` on first parse."""

        class _Headless(Dialect): ...

        with pytest.raises(AttributeError):
            _Headless.parse([{"role": "user"}], kind="messages")

    def test_subclass_must_bind_renderer(self) -> None:
        """A concrete dialect that omits :attr:`RENDERER` raises ``AttributeError`` on first render."""

        class _ParserOnly(Dialect):
            PARSER = _SilentParser

        with pytest.raises(AttributeError):
            _ = _ParserOnly.render([])

    def test_subclass_must_bind_assembler(self) -> None:
        """A concrete dialect that omits :attr:`ASSEMBLER` raises ``AttributeError`` on first assemble."""

        class _RendererOnly(Dialect):
            PARSER = _SilentParser
            RENDERER = _SilentRenderer

        async def _drive() -> None:
            await _RendererOnly.assemble(
                [
                    StartEvent(id="m", created=0),
                    TextEvent(channel="output", text="hi"),
                    StopEvent(stop_reason="stop"),
                ]
            )

        import asyncio

        with pytest.raises(AttributeError):
            asyncio.run(_drive())

    async def test_render_drives_renderer(self) -> None:
        events = [
            StartEvent(id="m", created=0),
            TextEvent(channel="output", text="hi"),
            StopEvent(stop_reason="stop"),
        ]

        out = [block async for block in _SilentDialect.render(events)]

        assert out == [TextEvent(channel="output", text="hi")]

    async def test_assemble_relays_to_assembler(self) -> None:
        events = [
            StartEvent(id="m", created=0, input_tokens=2),
            TextEvent(channel="output", text="hi"),
            StopEvent(stop_reason="stop", output_tokens=4),
        ]

        envelope = await _SilentDialect.assemble(events)

        assert envelope["start"] == StartEvent(id="m", created=0, input_tokens=2)
        assert envelope["stop"] == StopEvent(stop_reason="stop", output_tokens=4)
        assert envelope["events"] == [TextEvent(channel="output", text="hi")]
        assert envelope["kwargs"] == {}

    async def test_assemble_raises_on_error_stop(self) -> None:
        async def _source() -> t.AsyncIterator[Event]:
            yield StartEvent(id="m", created=0)
            yield TextEvent(channel="output", text="hi")
            raise RuntimeError("boom")

        with pytest.raises(LLMGenerationError):
            await _SilentDialect.assemble(_source())


class TestCaseRenderer:
    """Cover the :class:`Renderer` ABC contract surface (event-method coverage lives in test_buffer.py)."""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            Renderer()  # type: ignore[abstract]

    def test_default_skip_is_zero(self) -> None:
        renderer = _SilentRenderer()

        assert renderer.skip == 0


class TestCaseAssembler:
    """Cover the :class:`Assembler` ABC contract surface."""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            Assembler()  # type: ignore[abstract]

    def test_envelope_is_classmethod(self) -> None:
        envelope = _SilentAssembler.envelope(
            (TextEvent(channel="output", text="hi"),),
            start=StartEvent(id="m", created=0),
            stop=StopEvent(stop_reason="stop"),
        )

        assert envelope["events"] == [TextEvent(channel="output", text="hi")]


class TestCaseCoalescingRenderer:
    """Cover :class:`CoalescingRenderer` behaviour directly (engine integration lives in test_buffer.py).

    The renderer is exercised end-to-end through :class:`EventBuffer` in test_buffer.py; this test pins the
    direct behaviour of the FSM strategy so the contract is preserved when the engine itself changes.
    """

    def test_text_buffers_until_channel_change(self) -> None:
        renderer = CoalescingRenderer()

        assert list(renderer.on_text(TextEvent(channel="output", text="he"))) == []
        assert list(renderer.on_text(TextEvent(channel="output", text="llo"))) == []
        assert list(renderer.flush()) == [TextEvent(channel="output", text="hello")]

    def test_channel_transition_flushes_pending(self) -> None:
        renderer = CoalescingRenderer()
        list(renderer.on_text(TextEvent(channel="thinking", text="...")))

        out = list(renderer.on_text(TextEvent(channel="output", text="hi")))

        assert out == [TextEvent(channel="thinking", text="...")]

    def test_tool_passes_through_after_flush(self) -> None:
        renderer = CoalescingRenderer()
        list(renderer.on_text(TextEvent(channel="output", text="x")))

        tool = ToolEvent(id="c1", name="f", arguments={"a": 1})

        out = list(renderer.on_tool(tool))

        assert out == [TextEvent(channel="output", text="x"), tool]

    def test_on_stop_drops_lifecycle_marker(self) -> None:
        assert list(CoalescingRenderer().on_stop(StopEvent(stop_reason="stop"))) == []

    def test_flush_idempotent_when_idle(self) -> None:
        renderer = CoalescingRenderer()
        first = list(renderer.flush())
        second = list(renderer.flush())
        assert first == [] and second == []

    def test_typing_iterable_event(self) -> None:
        """Type-narrowing sanity: outputs are :class:`Event` (not the wire frame type)."""
        out: t.Iterable[Event] = CoalescingRenderer().flush()
        assert list(out) == []
