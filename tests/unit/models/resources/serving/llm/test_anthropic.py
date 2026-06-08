import typing as t
from unittest.mock import patch

import pytest

from flama.client import Client
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.models.resources.serving.llm.anthropic import MessagesMixin
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.serialize.data_structures import LLMModelCapabilities

SERVING = "anthropic"

ERROR_CASES = [
    pytest.param("query", False, "immediate", ValueError, "invalid params", 400, id="buffered_value_error_400"),
    pytest.param("query", False, "immediate", RuntimeError, "kaboom", 500, id="buffered_generic_exception_500"),
    pytest.param("stream", True, "immediate", ValueError, "bad stream args", 400, id="stream_value_error_400"),
    pytest.param("query", False, "iteration", RuntimeError, "mid-stream boom", 500, id="buffered_iteration_error_500"),
]


class TestCaseEndToEndMessages:
    """Cover the full HTTP path through Anthropic's ``/v1/messages`` endpoint.

    Exercises the message flattening pipeline (system as str / list, multi-tool-result expansion,
    assistant ``tool_use`` / ``thinking`` extraction), the ``thinking`` reasoning toggle precedence
    over the resource attribute and the backend capability gate, the streaming SSE event lifecycle,
    and the buffered envelope shape.
    """

    ENDPOINT = "/llm/anthropic/v1/messages"
    BODY = {"model": "stub", "max_tokens": 16, "messages": [{"role": "user", "content": "hi"}]}

    async def test_non_streaming_returns_envelope(self, client: Client) -> None:
        response = await client.post(
            "/llm/anthropic/v1/messages",
            json={
                "model": "stub",
                "max_tokens": 16,
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["type"] == "message"
        assert body["role"] == "assistant"
        assert body["model"] == "stub"
        assert body["id"].startswith("msg_")
        assert body["stop_reason"] == "end_turn"
        assert body["content"][0]["type"] == "text"

    async def test_streaming_returns_named_events(self, client: Client, llm_component) -> None:
        async def _mock_generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
            for token in ("hello", " world"):
                yield EngineDelta(text=token)
            yield EngineDelta(finish_reason="stop")

        with patch.object(type(llm_component.model.backend), "generate", _mock_generate):
            response = await client.post(
                "/llm/anthropic/v1/messages",
                json={
                    "model": "stub",
                    "max_tokens": 16,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )

        assert response.status_code == 200, response.text
        body = response.text
        assert "event: message_start" in body
        assert "event: content_block_start" in body
        assert "event: content_block_delta" in body
        assert "event: content_block_stop" in body
        assert "event: message_delta" in body
        assert "event: message_stop" in body
        assert "data: [DONE]" not in body

    async def test_tool_calls_route_through_stop_reason(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield ToolEvent(id="c1", name="lookup", arguments={"q": "x"})
                yield StopEvent(stop_reason="tool_use")

            return _gen()

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/anthropic/v1/messages",
                json={
                    "model": "stub",
                    "max_tokens": 16,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["stop_reason"] == "tool_use"
        tool = next(block for block in body["content"] if block["type"] == "tool_use")
        assert tool == {"type": "tool_use", "id": "c1", "name": "lookup", "input": {"q": "x"}}

    async def test_malformed_messages_rejected_with_400(self, client: Client) -> None:
        """A wire-shape violation surfaced by :meth:`AnthropicServing.parse` (here a ``system`` role,
        which Anthropic only accepts as a top-level field, not inside ``messages``) is translated into an
        HTTP 400 by the handler's parse guard."""
        response = await client.post(
            "/llm/anthropic/v1/messages",
            json={
                "model": "stub",
                "max_tokens": 16,
                "messages": [{"role": "system", "content": "be brief"}],
                "stream": False,
            },
        )

        assert response.status_code == 400, response.text

    async def test_thinking_routes_to_thinking_block(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield TextEvent(channel="thinking", text="reasoning bits")
                yield TextEvent(channel="output", text="final answer")
                yield StopEvent(stop_reason="stop")

            return _gen()

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/anthropic/v1/messages",
                json={
                    "model": "stub",
                    "max_tokens": 16,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )

        assert response.status_code == 200, response.text
        body = response.json()
        types_in_order = [block["type"] for block in body["content"]]
        assert types_in_order == ["thinking", "text"]

    @pytest.mark.parametrize(
        ["body_overrides", "resource_reasoning", "cap_reasoning", "expected_kwargs"],
        [
            pytest.param(
                {},
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": None},
                id="resource_on_capable_no_thinking_field",
            ),
            pytest.param(
                {},
                False,
                True,
                {"enable_thinking": False, "reasoning_effort": None},
                id="resource_off_short_circuits_capability",
            ),
            pytest.param(
                {},
                True,
                False,
                {"enable_thinking": False, "reasoning_effort": None},
                id="capability_gate_overrides_resource",
            ),
            pytest.param(
                {"thinking": {"type": "enabled", "budget_tokens": 1024}},
                False,
                True,
                {"enable_thinking": True, "reasoning_effort": 1024},
                id="thinking_enabled_overrides_resource_off",
            ),
            pytest.param(
                {"thinking": {"type": "enabled"}},
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": None},
                id="thinking_enabled_without_budget_keeps_effort_none",
            ),
            pytest.param(
                {"thinking": {"type": "disabled"}},
                True,
                True,
                {"enable_thinking": False, "reasoning_effort": None},
                id="thinking_disabled_overrides_resource_on",
            ),
            pytest.param(
                {"thinking": {"type": "enabled", "budget_tokens": 512}},
                True,
                False,
                {"enable_thinking": False, "reasoning_effort": None},
                id="capability_gate_overrides_thinking_field",
            ),
        ],
    )
    async def test_chat_template_kwargs_forwarded(
        self,
        client: Client,
        app,
        llm_component,
        capture_kwargs,
        body_overrides: dict[str, t.Any],
        resource_reasoning: bool,
        cap_reasoning: bool,
        expected_kwargs: dict[str, t.Any],
    ) -> None:
        """Verify the resource handler resolves ``enable_thinking`` from ``thinking.type`` (when set)
        / the resource's ``reasoning`` flag (default), gated by the backend's ``reasoning`` capability,
        and forwards ``budget_tokens`` through ``reasoning_effort``. Whenever thinking is gated off,
        ``reasoning_effort`` collapses to ``None``.
        """
        captured, mock = capture_kwargs
        body = {
            "model": "stub",
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            **body_overrides,
        }
        resource_cls = type(app.routes[0].resource)

        with (
            patch.object(resource_cls, "reasoning", resource_reasoning),
            patch.object(
                type(llm_component.model.backend),
                "capabilities",
                LLMModelCapabilities(text=True, reasoning=cap_reasoning),
            ),
            patch.object(type(llm_component.model), "query", mock),
        ):
            response = await client.post("/llm/anthropic/v1/messages", json=body)

        assert response.status_code == 200, response.text
        assert captured.get("chat_template_kwargs") == expected_kwargs

    @pytest.mark.parametrize(["method", "stream", "mode", "exception", "message", "status"], ERROR_CASES)
    async def test_error_propagation(
        self,
        client: Client,
        llm_component,
        method: str,
        stream: bool,
        mode: str,
        exception: type[Exception],
        message: str,
        status: int,
    ) -> None:
        if mode == "immediate":

            async def _mock(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
                raise exception(message)
        else:

            async def _mock(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
                async def _gen() -> t.AsyncIterator[t.Any]:
                    yield StartEvent(id="m", created=0)
                    yield TextEvent(channel="output", text="partial")
                    raise exception(message)

                return _gen()

        with patch.object(type(llm_component.model), method, _mock):
            response = await client.post(self.ENDPOINT, json={**self.BODY, "stream": stream})

        assert response.status_code == status, response.text
        if status == 400 and method == "query":
            assert message in response.text

    async def test_mismatched_model_name_logged(self, client: Client, caplog_flama) -> None:
        import logging

        with caplog_flama.at_level(logging.INFO, logger="flama.models.resources.serving.llm.anthropic"):
            await client.post(
                "/llm/anthropic/v1/messages",
                json={
                    "model": "claude-sonnet-4",
                    "max_tokens": 16,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )

        assert any("differs from resource" in rec.getMessage() for rec in caplog_flama.records)

    async def test_streaming_uses_ephemeral_buffer(self, client: Client, llm_component) -> None:
        from flama.models.streams import ModelStreams

        async def _mock_generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
            yield EngineDelta(text="hi")
            yield EngineDelta(finish_reason="stop")

        original = ModelStreams.create
        captured_persist: list[bool] = []

        async def _track(self, *, persist: bool = True):  # type: ignore[no-untyped-def]
            captured_persist.append(persist)
            return await original(self, persist=persist)

        with (
            patch.object(ModelStreams, "create", _track),
            patch.object(type(llm_component.model.backend), "generate", _mock_generate),
        ):
            response = await client.post(
                "/llm/anthropic/v1/messages",
                json={
                    "model": "stub",
                    "max_tokens": 16,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )

        assert response.status_code == 200, response.text
        assert captured_persist == [False]


class TestCaseEndToEndModels:
    """Cover ``GET /anthropic/v1/models``."""

    async def test_returns_single_entry_list(self, client: Client) -> None:
        response = await client.get("/llm/anthropic/v1/models")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["has_more"] is False
        assert body["first_id"] == "stub"
        assert body["last_id"] == "stub"
        assert len(body["data"]) == 1
        entry = body["data"][0]
        assert entry["id"] == "stub"
        assert entry["type"] == "model"
        assert entry["display_name"] == "stub"
        assert "created_at" in entry

    @pytest.mark.parametrize(
        ["capabilities", "expected"],
        [
            pytest.param(
                LLMModelCapabilities(text=True, image=True),
                {"vision": True, "audio": False, "tools": False, "reasoning": False},
                id="image",
            ),
            pytest.param(
                LLMModelCapabilities(text=True, audio=True),
                {"vision": False, "audio": True, "tools": False, "reasoning": False},
                id="audio",
            ),
            pytest.param(
                LLMModelCapabilities(text=True, tools=True),
                {"vision": False, "audio": False, "tools": True, "reasoning": False},
                id="tools",
            ),
            pytest.param(
                LLMModelCapabilities(text=True, reasoning=True),
                {"vision": False, "audio": False, "tools": False, "reasoning": True},
                id="reasoning",
            ),
            pytest.param(
                LLMModelCapabilities(text=True, image=True, audio=True, tools=True, reasoning=True),
                {"vision": True, "audio": True, "tools": True, "reasoning": True},
                id="all",
            ),
        ],
    )
    async def test_advertises_capabilities(
        self,
        client: Client,
        llm_component,
        capabilities: LLMModelCapabilities,
        expected: dict[str, bool],
    ) -> None:
        with patch.object(llm_component.model.backend, "capabilities", capabilities):
            response = await client.get("/llm/anthropic/v1/models")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data"][0]["capabilities"] == expected


class TestCaseResolveThinking:
    """Cover :meth:`MessagesMixin._resolve_thinking` resolution of the per-request ``thinking`` knob /
    the resource ``reasoning`` flag / the backend capability gate into ``(enable_thinking,
    reasoning_effort)``. The wire-translation helpers (system flattening, message expansion, tool
    spec parsing) live on :class:`AnthropicParser` and are covered by the parser unit tests.
    """

    @pytest.mark.parametrize(
        ["thinking", "resource_reasoning", "capability", "expected"],
        [
            pytest.param(None, True, True, (True, None), id="none_resource_on_capable"),
            pytest.param(None, False, True, (False, None), id="none_resource_off_capable"),
            pytest.param(None, True, False, (False, None), id="capability_off_dominates"),
            pytest.param(
                {"type": "enabled", "budget_tokens": 256}, False, True, (True, 256), id="enabled_overrides_resource"
            ),
            pytest.param({"type": "enabled"}, True, True, (True, None), id="enabled_without_budget"),
            pytest.param({"type": "disabled"}, True, True, (False, None), id="disabled_overrides_resource"),
            pytest.param(
                {"type": "enabled", "budget_tokens": 1},
                False,
                False,
                (False, None),
                id="capability_off_dominates_field",
            ),
            pytest.param({"type": "weird"}, True, True, (True, None), id="unknown_type_falls_back_to_resource"),
        ],
    )
    def test_resolve_thinking(
        self,
        thinking: t.Any,
        resource_reasoning: bool,
        capability: bool,
        expected: tuple[bool, t.Any],
    ) -> None:
        assert (
            MessagesMixin._resolve_thinking(thinking, resource_reasoning=resource_reasoning, capability=capability)
            == expected
        )
