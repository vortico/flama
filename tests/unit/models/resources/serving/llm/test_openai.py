import typing as t
from unittest.mock import patch

import pytest

from flama.client import Client
from flama.exceptions import FrameworkNotInstalled, HTTPException
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.resources.serving.llm.openai import OpenAIServing, ResponsesMixin
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    AudioURI,
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
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.serialize.data_structures import LLMModelCapabilities

SERVING = "openai"

ERROR_CASES = [
    pytest.param("query", False, "immediate", ValueError, "invalid params", 400, id="buffered_value_error_400"),
    pytest.param("query", False, "immediate", RuntimeError, "kaboom", 500, id="buffered_generic_exception_500"),
    pytest.param("stream", True, "immediate", ValueError, "bad stream args", 400, id="stream_value_error_400"),
    pytest.param("query", False, "iteration", RuntimeError, "mid-stream boom", 500, id="buffered_iteration_error_500"),
]


class TestCaseEndToEndChatCompletions:
    """Cover the full HTTP path through the OpenAI dialect's ``/v1/chat/completions`` and
    ``/v1/responses`` endpoints — both go through the same :class:`OpenAIServing` resource handler so
    we exercise them together to keep the surface coherent (the ``enable_thinking`` precedence test in
    particular spans both routes since the handler computes the toggle once per request).
    """

    ENDPOINT = "/llm/openai/v1/chat/completions"
    BODY = {"model": "stub", "messages": [{"role": "user", "content": "hi"}]}

    async def test_non_streaming_returns_envelope(self, client: Client) -> None:
        response = await client.post(
            "/llm/openai/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["object"] == "chat.completion"
        assert body["model"] == "stub"
        assert body["id"].startswith("chatcmpl-")
        choice = body["choices"][0]
        assert choice["message"]["role"] == "assistant"
        assert choice["finish_reason"] == "stop"

    async def test_streaming_returns_sse_chunks_with_done_sentinel(self, client: Client, llm_component) -> None:
        async def _mock_generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
            for token in ("hello", " ", "world"):
                yield EngineDelta(text=token)
            yield EngineDelta(finish_reason="stop")

        with patch.object(type(llm_component.model.backend), "generate", _mock_generate):
            response = await client.post(
                "/llm/openai/v1/chat/completions",
                json={
                    "model": "stub",
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": True,
                },
            )

        assert response.status_code == 200, response.text
        assert "text/event-stream" in response.headers.get("content-type", "")
        body = response.text
        assert "data: [DONE]" in body
        assert '"object":"chat.completion.chunk"' in body
        assert '"role":"assistant"' in body

    @pytest.mark.parametrize(
        ["structured_part", "expected_modality"],
        [
            pytest.param(
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                "image",
                id="image_url",
            ),
            pytest.param(
                {"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}},
                "audio",
                id="input_audio",
            ),
        ],
    )
    async def test_multimodal_request_rejected_on_text_only_backend(
        self, client: Client, structured_part: dict[str, t.Any], expected_modality: str
    ) -> None:
        response = await client.post(
            "/llm/openai/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "describe"},
                            structured_part,
                        ],
                    }
                ],
                "stream": False,
            },
        )

        assert response.status_code == 400, response.text
        assert expected_modality in response.text.lower()

    async def test_malformed_messages_rejected_with_400(self, client: Client) -> None:
        """A wire-shape violation surfaced by :meth:`OpenAIServing.parse` (here ``tool_call_id`` on a
        non-``tool`` role) is translated into an HTTP 400 by the handler's parse guard rather than
        bubbling up as a 500."""
        response = await client.post(
            "/llm/openai/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "hi", "tool_call_id": "c1"}],
                "stream": False,
            },
        )

        assert response.status_code == 400, response.text
        assert "tool_call_id" in response.text

    async def test_tool_calls_route_through_stop_reason(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield ToolEvent(id="c1", name="lookup", arguments={"q": "x"})
                yield StopEvent(stop_reason="tool_use")

            return _gen()

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/openai/v1/chat/completions",
                json={
                    "model": "stub",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )

        assert response.status_code == 200, response.text
        choice = response.json()["choices"][0]
        assert choice["finish_reason"] == "tool_calls"
        assert choice["message"]["tool_calls"][0]["function"]["name"] == "lookup"

    async def test_buffered_thinking_stamps_reasoning_field(self, client: Client, llm_component) -> None:
        """The non-streaming response routes thinking onto ``message.reasoning_content`` and keeps
        ``message.content`` clean, so legacy clients render the answer untouched and reasoning-aware clients
        pick up the structured field."""

        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield TextEvent(channel="thinking", text="reasoning bits")
                yield TextEvent(channel="output", text="final answer")
                yield StopEvent(stop_reason="stop")

            return _gen()

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/openai/v1/chat/completions",
                json={"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": False},
            )

        assert response.status_code == 200, response.text
        message = response.json()["choices"][0]["message"]
        assert message["content"] == "final answer"
        assert message["reasoning_content"] == "reasoning bits"

    async def test_streaming_emits_reasoning_content_on_thought_deltas(self, client: Client, llm_component) -> None:
        """The streamed response carries thought fragments on ``delta.reasoning_content`` (with ``delta.content``
        omitted) and answer fragments on ``delta.content``, so editor plugins that target the structured field
        render a thinking pane without buffering for the whole turn."""

        async def _mock_stream(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield TextEvent(channel="thinking", text="thought")
                yield TextEvent(channel="output", text="answer")
                yield StopEvent(stop_reason="stop")

            return _gen()

        with patch.object(type(llm_component.model), "stream", _mock_stream):
            response = await client.post(
                "/llm/openai/v1/chat/completions",
                json={"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            )

        assert response.status_code == 200, response.text
        body = response.text
        assert "<think>" not in body
        assert "</think>" not in body
        assert '"reasoning_content":"thought"' in body
        assert '"content":"answer"' in body

    async def test_responses_non_streaming_returns_response_object(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0, input_tokens=3)
                yield TextEvent(channel="thinking", text="thought")
                yield TextEvent(channel="output", text="answer")
                yield StopEvent(stop_reason="stop", output_tokens=2)

            return _gen()

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/openai/v1/responses",
                json={"model": "stub", "input": "hi", "stream": False},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["object"] == "response"
        assert body["status"] == "completed"
        assert body["usage"] == {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
        assert [item["type"] for item in body["output"]] == ["reasoning", "message"]

    async def test_responses_streaming_returns_named_events(self, client: Client, llm_component) -> None:
        async def _mock_stream(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0, input_tokens=3)
                yield TextEvent(channel="thinking", text="thought")
                yield TextEvent(channel="output", text="answer")
                yield StopEvent(stop_reason="stop", output_tokens=2)

            return _gen()

        with patch.object(type(llm_component.model), "stream", _mock_stream):
            response = await client.post(
                "/llm/openai/v1/responses",
                json={"model": "stub", "input": "hi", "stream": True},
            )

        assert response.status_code == 200, response.text
        assert "event: response.created" in response.text
        assert "event: response.reasoning_summary_text.delta" in response.text
        assert "event: response.output_text.delta" in response.text
        assert "data: [DONE]" not in response.text

    @pytest.mark.parametrize(
        ["endpoint", "body", "method", "resource_reasoning", "cap_reasoning", "expected_kwargs"],
        [
            pytest.param(
                "/llm/openai/v1/chat/completions",
                {"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": False},
                "query",
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": None},
                id="chat_completions_buffered_resource_on_capable",
            ),
            pytest.param(
                "/llm/openai/v1/chat/completions",
                {"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": True},
                "stream",
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": None},
                id="chat_completions_stream_resource_on_capable",
            ),
            pytest.param(
                "/llm/openai/v1/responses",
                {"model": "stub", "input": "hi", "stream": False},
                "query",
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": None},
                id="responses_buffered_resource_on_capable",
            ),
            pytest.param(
                "/llm/openai/v1/responses",
                {"model": "stub", "input": "hi", "stream": True},
                "stream",
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": None},
                id="responses_stream_resource_on_capable",
            ),
            pytest.param(
                "/llm/openai/v1/chat/completions",
                {"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": False},
                "query",
                False,
                True,
                {"enable_thinking": False, "reasoning_effort": None},
                id="resource_off_short_circuits_capability",
            ),
            pytest.param(
                "/llm/openai/v1/chat/completions",
                {"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": False},
                "query",
                True,
                False,
                {"enable_thinking": False, "reasoning_effort": None},
                id="capability_gate_overrides_resource",
            ),
            pytest.param(
                "/llm/openai/v1/chat/completions",
                {"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": False},
                "query",
                False,
                False,
                {"enable_thinking": False, "reasoning_effort": None},
                id="both_off",
            ),
            pytest.param(
                "/llm/openai/v1/chat/completions",
                {
                    "model": "stub",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "reasoning_effort": "low",
                },
                "query",
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": "low"},
                id="chat_completions_reasoning_effort_low",
            ),
            pytest.param(
                "/llm/openai/v1/chat/completions",
                {
                    "model": "stub",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "reasoning_effort": "max",
                },
                "query",
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": "max"},
                id="chat_completions_reasoning_effort_off_spec_passes_through",
            ),
            pytest.param(
                "/llm/openai/v1/chat/completions",
                {
                    "model": "stub",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "reasoning_effort": "low",
                },
                "query",
                False,
                True,
                {"enable_thinking": False, "reasoning_effort": None},
                id="reasoning_effort_dropped_when_thinking_disabled",
            ),
            pytest.param(
                "/llm/openai/v1/responses",
                {
                    "model": "stub",
                    "input": "hi",
                    "stream": False,
                    "reasoning": {"effort": "high"},
                },
                "query",
                True,
                True,
                {"enable_thinking": True, "reasoning_effort": "high"},
                id="responses_reasoning_object_effort_extracted",
            ),
        ],
    )
    async def test_chat_template_kwargs_forwarded(
        self,
        client: Client,
        app,
        llm_component,
        capture_kwargs,
        endpoint: str,
        body: dict[str, t.Any],
        method: str,
        resource_reasoning: bool,
        cap_reasoning: bool,
        expected_kwargs: dict[str, t.Any],
    ) -> None:
        """Verify the resource handler resolves ``enable_thinking = resource.reasoning and cap.reasoning``
        and forwards both that bool and the per-request ``reasoning_effort`` (chat-completions body field
        or ``reasoning.effort`` on Responses) verbatim through ``chat_template_kwargs``. ``reasoning_effort``
        is unvalidated — off-spec values pass through like ``temperature`` — and is dropped to ``None``
        whenever thinking is gated off.
        """
        captured, mock = capture_kwargs
        resource_cls = type(app.routes[0].resource)

        with (
            patch.object(resource_cls, "reasoning", resource_reasoning),
            patch.object(
                type(llm_component.model.backend),
                "capabilities",
                LLMModelCapabilities(text=True, reasoning=cap_reasoning),
            ),
            patch.object(type(llm_component.model), method, mock),
        ):
            response = await client.post(endpoint, json=body)

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

    async def test_max_completion_tokens_aliases_to_max_tokens(
        self, client: Client, llm_component, capture_kwargs
    ) -> None:
        captured, mock = capture_kwargs

        with patch.object(type(llm_component.model), "query", mock):
            response = await client.post(
                "/llm/openai/v1/chat/completions",
                json={
                    "model": "stub",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "max_completion_tokens": 16,
                },
            )

        assert response.status_code == 200, response.text
        assert captured.get("max_tokens") == 16

    async def test_mismatched_model_name_logged(self, client: Client, caplog_flama) -> None:
        import logging

        with caplog_flama.at_level(logging.INFO, logger="flama.models.resources.serving.llm.openai"):
            await client.post(
                "/llm/openai/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
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
                "/llm/openai/v1/chat/completions",
                json={"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            )

        assert response.status_code == 200, response.text
        assert captured_persist == [False]


class TestCaseEndToEndCompletions:
    """Cover the legacy completions endpoint."""

    ENDPOINT = "/llm/openai/v1/completions"
    BODY = {"model": "stub", "prompt": "hi"}

    async def test_non_streaming_returns_text_envelope(self, client: Client) -> None:
        response = await client.post(
            "/llm/openai/v1/completions",
            json={"model": "stub", "prompt": "hello world", "stream": False},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["object"] == "text_completion"
        assert body["id"].startswith("cmpl-")
        assert body["choices"][0]["finish_reason"] == "stop"
        assert isinstance(body["choices"][0]["text"], str)

    async def test_streaming_returns_sse(self, client: Client, llm_component) -> None:
        async def _mock_generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
            for token in ("foo", " bar"):
                yield EngineDelta(text=token)
            yield EngineDelta(finish_reason="stop")

        with patch.object(type(llm_component.model.backend), "generate", _mock_generate):
            response = await client.post(
                "/llm/openai/v1/completions",
                json={"model": "stub", "prompt": "hi", "stream": True},
            )

        assert response.status_code == 200, response.text
        body = response.text
        assert "data: [DONE]" in body
        assert '"object":"text_completion"' in body

    async def test_missing_prompt_returns_400(self, client: Client) -> None:
        response = await client.post(
            "/llm/openai/v1/completions",
            json={"model": "stub", "stream": False},
        )

        assert response.status_code == 400, response.text

    async def test_non_string_prompt_returns_400(self, client: Client) -> None:
        """A schema-valid but non-string ``prompt`` (here an empty list, which collapses to a non-string
        value after the list-unwrap) is rejected with HTTP 400 by the handler's prompt guard."""
        response = await client.post(
            "/llm/openai/v1/completions",
            json={"model": "stub", "prompt": [], "stream": False},
        )

        assert response.status_code == 400, response.text

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(FrameworkNotInstalled, id="framework_not_installed")],
        indirect=["exception"],
    )
    async def test_buffered_framework_not_installed_propagates(self, client: Client, llm_component, exception) -> None:
        """``FrameworkNotInstalled`` raised by ``model.query`` is re-raised verbatim (not downgraded to an
        HTTP 400 / 500) so the missing-runtime failure surfaces to the ASGI server unchanged."""

        async def _mock(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise FrameworkNotInstalled("vllm or mlx-lm")

        with patch.object(type(llm_component.model), "query", _mock), exception:
            await client.post("/llm/openai/v1/completions", json={"model": "stub", "prompt": "hi", "stream": False})

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

    async def test_max_completion_tokens_aliases_to_max_tokens(
        self, client: Client, llm_component, capture_kwargs
    ) -> None:
        captured, mock = capture_kwargs

        with patch.object(type(llm_component.model), "query", mock):
            response = await client.post(
                "/llm/openai/v1/completions",
                json={"model": "stub", "prompt": "hi", "stream": False, "max_completion_tokens": 8},
            )

        assert response.status_code == 200, response.text
        assert captured.get("max_tokens") == 8

    async def test_mismatched_model_name_logged(self, client: Client, caplog_flama) -> None:
        import logging

        with caplog_flama.at_level(logging.INFO, logger="flama.models.resources.serving.llm.openai"):
            await client.post(
                "/llm/openai/v1/completions",
                json={"model": "gpt-3.5-turbo", "prompt": "hi", "stream": False},
            )

        assert any("differs from resource" in rec.getMessage() for rec in caplog_flama.records)


class TestCaseResponsesMessagesFromInput:
    """Cover :meth:`ResponsesMixin._messages_from_input` translation of the Responses ``input`` field.

    Exercised directly (rather than through the endpoint) because the schema layer coerces / rejects the
    non-string-non-list ``input`` shape before it reaches the handler, so the invalid-type guard is only
    reachable at the unit level. Covers the string fast-path, the list-of-items expansion (role default,
    ``content`` -> ``text`` fallback, ``tool_calls`` / ``tool_call_id`` pass-through, non-dict items
    filtered out), the ``instructions`` -> leading system-message injection, and the invalid-type guard.
    """

    @pytest.mark.parametrize(
        ["input_", "instructions", "expected", "exception"],
        [
            pytest.param("hi", None, [{"role": "user", "content": "hi"}], None, id="string_input"),
            pytest.param(
                "hi",
                "be brief",
                [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}],
                None,
                id="string_input_with_instructions",
            ),
            pytest.param(
                [
                    {"role": "user", "content": "hi"},
                    {"role": "assistant", "tool_calls": [{"id": "c1"}]},
                    {"role": "tool", "tool_call_id": "c1", "content": "42"},
                    {"text": "from-text-field"},
                    "skip-me",
                ],
                None,
                [
                    {"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
                    {"role": "tool", "content": "42", "tool_call_id": "c1"},
                    {"role": "user", "content": "from-text-field"},
                ],
                None,
                id="list_items",
            ),
            pytest.param(123, None, None, HTTPException, id="invalid_type_raises_400"),
        ],
        indirect=["exception"],
    )
    def test_messages_from_input(
        self,
        input_: t.Any,
        instructions: str | None,
        expected: list[dict[str, t.Any]] | None,
        exception,
    ) -> None:
        with exception as exc_info:
            assert ResponsesMixin._messages_from_input(input_, instructions) == expected
        if exception:
            assert exc_info.value.status_code == 400


class TestCaseEndToEndResponses:
    """Cover the OpenAI Responses endpoint's parse-error guard and param plumbing.

    The streaming / buffered envelope shapes are exercised in
    :class:`TestCaseEndToEndChatCompletions`; the ``input`` normalisation is exercised by
    :class:`TestCaseResponsesMessagesFromInput`. This suite pins the parse-error guard and the
    ``max_output_tokens`` / ``max_completion_tokens`` -> ``max_tokens`` aliasing alongside the
    mismatched-model log path.
    """

    ENDPOINT = "/llm/openai/v1/responses"

    async def test_input_parse_error_returns_400(self, client: Client) -> None:
        """A list ``input`` whose normalised messages violate the wire contract (``tool_call_id`` on a
        non-``tool`` role) is rejected with HTTP 400 by the parse guard."""
        response = await client.post(
            "/llm/openai/v1/responses",
            json={
                "model": "stub",
                "input": [{"role": "user", "content": "hi", "tool_call_id": "c1"}],
                "stream": False,
            },
        )

        assert response.status_code == 400, response.text

    async def test_token_aliases_and_model_mismatch(self, client: Client, llm_component, capture_kwargs) -> None:
        """``max_output_tokens`` aliases to ``max_tokens`` (winning over ``max_completion_tokens`` via
        ``setdefault``), and a body ``model`` differing from the resource name is accepted (logged, not
        rejected)."""
        captured, mock = capture_kwargs

        with patch.object(type(llm_component.model), "query", mock):
            response = await client.post(
                "/llm/openai/v1/responses",
                json={
                    "model": "gpt-4o",
                    "input": "hi",
                    "stream": False,
                    "max_output_tokens": 16,
                    "max_completion_tokens": 8,
                },
            )

        assert response.status_code == 200, response.text
        assert captured.get("max_tokens") == 16


class TestCaseEndToEndModels:
    """Cover ``GET /openai/v1/models``."""

    async def test_returns_single_entry_list(self, client: Client) -> None:
        response = await client.get("/llm/openai/v1/models")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["object"] == "list"
        assert len(body["data"]) == 1
        entry = body["data"][0]
        assert entry["id"] == "stub"
        assert entry["object"] == "model"
        assert entry["owned_by"] == "flama"
        assert entry["capabilities"] == {"vision": False, "audio": False, "tools": False, "reasoning": False}

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
            response = await client.get("/llm/openai/v1/models")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data"][0]["capabilities"] == expected


class TestCaseOpenAIServingParse:
    """Cover :meth:`OpenAIServing.parse` translation from OpenAI wire format to canonical L2 Messages.

    These tests exercise the LLMServing façade with ``kind="messages"`` over a single-element list to
    pin down the dialect-specific OpenAI content-part coverage; the symmetric tool-list façade and
    the cross-dialect delegation matrix are exercised in
    :mod:`tests.unit.models.resources.serving.llm.test_base`.
    """

    @pytest.mark.parametrize(
        ["value", "expected", "exception"],
        [
            pytest.param(
                {"role": "user", "content": "hi"},
                (UserMessage(content=(TextContent(text="hi"),)),),
                None,
                id="user_string_content",
            ),
            pytest.param(
                {"role": "system", "content": "be brief"},
                (SystemMessage(content=(TextContent(text="be brief"),)),),
                None,
                id="system_string_content",
            ),
            pytest.param(
                {"role": "assistant", "content": "ok"},
                (AssistantMessage(content=(TextContent(text="ok"),)),),
                None,
                id="assistant_string_content",
            ),
            pytest.param(
                {"role": "tool", "tool_call_id": "c1", "content": "42"},
                (ToolMessage(tool_call_id="c1", content=(TextContent(text="42"),)),),
                None,
                id="tool_role",
            ),
            pytest.param(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}},
                    ],
                },
                (
                    AssistantMessage(
                        tool_calls=(ToolCall(id="c1", function={"name": "f", "arguments": "{}"}),),
                    ),
                ),
                None,
                id="assistant_tool_calls_only",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image_url", "image_url": {"url": "https://cdn.example/img.png"}},
                    ],
                },
                (
                    UserMessage(
                        content=(
                            TextContent(text="describe"),
                            ImageURL(source=SourceURL(url="https://cdn.example/img.png")),
                        ),
                    ),
                ),
                None,
                id="text_and_image_url",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,QUFB"}}],
                },
                (UserMessage(content=(ImageURI(source=SourceURI(data="QUFB"), format="png"),)),),
                None,
                id="image_url_data_uri_collapses_to_uri",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [{"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}}],
                },
                (UserMessage(content=(AudioURI(source=SourceURI(data="AAAA"), format="wav"),)),),
                None,
                id="input_audio",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "video_url", "video_url": {"url": "x"}}]},
                None,
                (LLMUnsupportedContentPart, "Wrong content part type 'video_url'"),
                id="unsupported_part_type",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x", "detail": "ultra"}}]},
                None,
                (ValueError, "Wrong image detail"),
                id="invalid_detail",
            ),
            pytest.param(
                {"role": "user", "content": "x", "tool_call_id": "c1"},
                None,
                (ValueError, "'tool_call_id' is only allowed when role is 'tool'"),
                id="user_with_tool_call_id",
            ),
        ],
        indirect=["exception"],
    )
    def test_parse(self, value: dict[str, t.Any], expected: tuple[Message, ...] | None, exception) -> None:
        with exception:
            assert OpenAIServing.parse([value], kind="messages") == expected
