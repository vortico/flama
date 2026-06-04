import json
import typing as t
from unittest.mock import patch

import pytest

from flama.client import Client
from flama.models import LLMResource, LLMResourceType
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.resources.serving.llm.ollama import OllamaServing
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    ImageURI,
    ImageURL,
    Message,
    SourceURI,
    SourceURL,
    TextContent,
    ToolCall,
    UserMessage,
)
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.serialize.data_structures import LLMModelCapabilities


def _parse_ndjson(body: str) -> list[dict[str, t.Any]]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


class TestCaseEndToEndChat:
    """Cover the full HTTP path through ``POST /ollama/api/chat``."""

    @pytest.fixture(scope="function")
    async def client(self, app, llm_component) -> t.AsyncIterator[Client]:
        component_ = llm_component

        class StubLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "stub"
            verbose_name = "Stub LLM"
            component = component_
            heartbeat_interval = 0
            serving = ("ollama",)

        app.models.add_model_resource("/llm/", StubLLMResource)

        async with Client(app=app) as client:
            yield client

    @pytest.fixture(scope="function")
    async def client_with_resource(self, app, llm_component) -> t.AsyncIterator[tuple[Client, type]]:
        """Variant of :meth:`client` that also exposes the dynamically built ``StubLLMResource`` class.

        ``test_think_resolution`` needs to patch ``reasoning`` on the resource between parametrisations
        (without rebuilding the app), so the fixture surfaces both handles. Sibling tests keep using
        the simpler :meth:`client` fixture so this addition doesn't ripple through the rest of the
        class.
        """
        component_ = llm_component

        class StubLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "stub"
            verbose_name = "Stub LLM"
            component = component_
            heartbeat_interval = 0
            serving = ("ollama",)

        app.models.add_model_resource("/llm/", StubLLMResource)

        async with Client(app=app) as client:
            yield client, StubLLMResource

    @staticmethod
    def _capture_kwargs() -> tuple[dict[str, t.Any], t.Callable[..., t.AsyncIterator[t.Any]]]:
        """Build a ``(captured, mock)`` pair where ``captured`` records the kwargs the resource
        forwards to :meth:`Model.query` / :meth:`Model.stream` and ``mock`` plays a minimal valid
        event sequence so the HTTP layer reaches a 200.
        """
        captured: dict[str, t.Any] = {}

        async def _mock(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            captured.update(kwargs)

            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield TextEvent(channel="output", text="ok")
                yield StopEvent(stop_reason="stop")

            return _gen()

        return captured, _mock

    async def test_non_streaming_returns_envelope(self, client: Client) -> None:
        response = await client.post(
            "/llm/ollama/api/chat",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["model"] == "stub"
        assert body["done"] is True
        assert body["done_reason"] == "stop"
        assert body["message"]["role"] == "assistant"

    async def test_streaming_returns_ndjson_frames_with_terminal_done(self, client: Client, llm_component) -> None:
        async def _mock_generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
            for token in ("hello", " ", "world"):
                yield EngineDelta(text=token)
            yield EngineDelta(finish_reason="stop")

        with patch.object(type(llm_component.model.backend), "generate", _mock_generate):
            response = await client.post(
                "/llm/ollama/api/chat",
                json={
                    "model": "stub",
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": True,
                },
            )

        assert response.status_code == 200, response.text
        assert "application/x-ndjson" in response.headers.get("content-type", "")
        frames = _parse_ndjson(response.text)
        assert frames[-1]["done"] is True
        assert frames[-1]["done_reason"] == "stop"
        assert any(not f.get("done") and f.get("message", {}).get("content") for f in frames[:-1])

    async def test_images_request_rejected_on_text_only_backend(self, client: Client) -> None:
        response = await client.post(
            "/llm/ollama/api/chat",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "describe", "images": ["abc"]}],
                "stream": False,
            },
        )

        assert response.status_code == 400, response.text
        assert "image" in response.text.lower()

    async def test_tool_calls_route_through_buffered_response(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield ToolEvent(id="c1", name="lookup", arguments={"q": "x"})
                yield StopEvent(stop_reason="tool_use")

            return _gen()

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/ollama/api/chat",
                json={
                    "model": "stub",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["done_reason"] == "stop"
        tool_calls = body["message"]["tool_calls"]
        assert tool_calls[0]["function"]["name"] == "lookup"
        assert tool_calls[0]["function"]["arguments"] == {"q": "x"}

    async def test_buffered_value_error_returns_400(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise ValueError("invalid params")

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/ollama/api/chat",
                json={"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": False},
            )

        assert response.status_code == 400, response.text

    async def test_buffered_generic_exception_returns_500(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise RuntimeError("kaboom")

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/ollama/api/chat",
                json={"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": False},
            )

        assert response.status_code == 500, response.text

    async def test_stream_value_error_returns_400(self, client: Client, llm_component) -> None:
        async def _mock_stream(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise ValueError("bad stream args")

        with patch.object(type(llm_component.model), "stream", _mock_stream):
            response = await client.post(
                "/llm/ollama/api/chat",
                json={"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            )

        assert response.status_code == 400, response.text

    async def test_mismatched_model_name_logged(self, client: Client, caplog) -> None:
        import logging

        with caplog.at_level(logging.INFO, logger="flama.models.resources.serving.llm.ollama"):
            await client.post(
                "/llm/ollama/api/chat",
                json={
                    "model": "llama3",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )

        assert any("differs from resource" in rec.getMessage() for rec in caplog.records)

    async def test_buffered_iteration_error_returns_500(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield TextEvent(channel="output", text="partial")
                raise RuntimeError("mid-stream boom")

            return _gen()

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/ollama/api/chat",
                json={"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": False},
            )

        assert response.status_code == 500, response.text

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
                "/llm/ollama/api/chat",
                json={"model": "stub", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            )

        assert response.status_code == 200, response.text
        assert captured_persist == [False]

    @pytest.mark.parametrize(
        ["resource_reasoning", "body_think", "cap_reasoning", "expected"],
        [
            pytest.param(True, None, True, True, id="default_capable_falls_back_to_on"),
            pytest.param(False, None, True, False, id="default_off_falls_back_to_off"),
            pytest.param(True, True, True, True, id="explicit_true_when_capable"),
            pytest.param(True, False, True, False, id="explicit_false_overrides_default"),
            pytest.param(False, True, True, True, id="explicit_true_overrides_off_default"),
            pytest.param(True, True, False, False, id="capability_gate_clamps_to_false"),
            pytest.param(True, None, False, False, id="capability_gate_with_default"),
        ],
    )
    async def test_think_resolution(
        self,
        client_with_resource: tuple[Client, type],
        llm_component,
        resource_reasoning: bool,
        body_think: bool | None,
        cap_reasoning: bool,
        expected: bool,
    ) -> None:
        """Verify the resource-handler precedence for ``think`` on ``POST /ollama/api/chat``: the
        handler falls back to the resource-level :attr:`LLMResource.reasoning` bool when the body
        omits ``think``. Per-request ``think`` always wins over the fallback, and the model-capability
        gate clamps the result to :data:`False` whenever the underlying model doesn't expose
        ``enable_thinking``.
        """
        client_, resource_cls = client_with_resource
        captured, mock = self._capture_kwargs()
        body: dict[str, t.Any] = {
            "model": "stub",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        }
        if body_think is not None:
            body["think"] = body_think

        with (
            patch.object(resource_cls, "reasoning", resource_reasoning),
            patch.object(
                type(llm_component.model.backend),
                "capabilities",
                LLMModelCapabilities(text=True, reasoning=cap_reasoning),
            ),
            patch.object(type(llm_component.model), "query", mock),
        ):
            response = await client_.post("/llm/ollama/api/chat", json=body)

        assert response.status_code == 200, response.text
        assert captured.get("chat_template_kwargs") == {"enable_thinking": expected}


class TestCaseEndToEndGenerate:
    """Cover the raw generation endpoint at ``POST /ollama/api/generate``."""

    @pytest.fixture(scope="function")
    async def client(self, app, llm_component) -> t.AsyncIterator[Client]:
        component_ = llm_component

        class StubLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "stub"
            verbose_name = "Stub LLM"
            component = component_
            heartbeat_interval = 0
            serving = ("ollama",)

        app.models.add_model_resource("/llm/", StubLLMResource)

        async with Client(app=app) as client:
            yield client

    async def test_non_streaming_returns_envelope(self, client: Client) -> None:
        response = await client.post(
            "/llm/ollama/api/generate",
            json={"model": "stub", "prompt": "hello world", "stream": False},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["model"] == "stub"
        assert body["done"] is True
        assert body["done_reason"] == "stop"
        assert isinstance(body["response"], str)

    async def test_streaming_returns_ndjson(self, client: Client, llm_component) -> None:
        async def _mock_generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
            for token in ("foo", " bar"):
                yield EngineDelta(text=token)
            yield EngineDelta(finish_reason="stop")

        with patch.object(type(llm_component.model.backend), "generate", _mock_generate):
            response = await client.post(
                "/llm/ollama/api/generate",
                json={"model": "stub", "prompt": "hi", "stream": True},
            )

        assert response.status_code == 200, response.text
        frames = _parse_ndjson(response.text)
        assert frames[-1]["done"] is True
        assert "".join(f["response"] for f in frames if not f.get("done")) == "foo bar"

    async def test_missing_prompt_returns_400(self, client: Client) -> None:
        response = await client.post(
            "/llm/ollama/api/generate",
            json={"model": "stub", "prompt": "", "stream": False},
        )

        assert response.status_code == 400, response.text

    async def test_buffered_value_error_returns_400(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise ValueError("invalid params")

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/ollama/api/generate",
                json={"model": "stub", "prompt": "hi", "stream": False},
            )

        assert response.status_code == 400, response.text

    async def test_buffered_generic_exception_returns_500(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise RuntimeError("kaboom")

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/ollama/api/generate",
                json={"model": "stub", "prompt": "hi", "stream": False},
            )

        assert response.status_code == 500, response.text

    async def test_stream_value_error_returns_400(self, client: Client, llm_component) -> None:
        async def _mock_stream(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise ValueError("bad stream args")

        with patch.object(type(llm_component.model), "stream", _mock_stream):
            response = await client.post(
                "/llm/ollama/api/generate",
                json={"model": "stub", "prompt": "hi", "stream": True},
            )

        assert response.status_code == 400, response.text

    async def test_mismatched_model_name_logged(self, client: Client, caplog) -> None:
        import logging

        with caplog.at_level(logging.INFO, logger="flama.models.resources.serving.llm.ollama"):
            await client.post(
                "/llm/ollama/api/generate",
                json={"model": "llama3", "prompt": "hi", "stream": False},
            )

        assert any("differs from resource" in rec.getMessage() for rec in caplog.records)

    async def test_buffered_iteration_error_returns_500(self, client: Client, llm_component) -> None:
        async def _mock_query(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
            async def _gen() -> t.AsyncIterator[t.Any]:
                yield StartEvent(id="m", created=0)
                yield TextEvent(channel="output", text="partial")
                raise RuntimeError("mid-stream boom")

            return _gen()

        with patch.object(type(llm_component.model), "query", _mock_query):
            response = await client.post(
                "/llm/ollama/api/generate",
                json={"model": "stub", "prompt": "hi", "stream": False},
            )

        assert response.status_code == 500, response.text


class TestCaseEndToEndTags:
    """Cover ``GET /ollama/api/tags``."""

    @pytest.fixture(scope="function")
    async def client(self, app, llm_component) -> t.AsyncIterator[Client]:
        component_ = llm_component

        class StubLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "stub"
            verbose_name = "Stub LLM"
            component = component_
            heartbeat_interval = 0
            serving = ("ollama",)

        app.models.add_model_resource("/llm/", StubLLMResource)

        async with Client(app=app) as client:
            yield client

    async def test_returns_single_entry_list(self, client: Client) -> None:
        response = await client.get("/llm/ollama/api/tags")

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["models"]) == 1
        entry = body["models"][0]
        assert entry["name"] == "stub"
        assert entry["model"] == "stub"


class TestCaseEndToEndVersion:
    """Cover ``GET /ollama/api/version``."""

    @pytest.fixture(scope="function")
    async def client(self, app, llm_component) -> t.AsyncIterator[Client]:
        component_ = llm_component

        class StubLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "stub"
            verbose_name = "Stub LLM"
            component = component_
            heartbeat_interval = 0
            serving = ("ollama",)

        app.models.add_model_resource("/llm/", StubLLMResource)

        async with Client(app=app) as client:
            yield client

    async def test_returns_flama_package_version(self, client: Client) -> None:
        response = await client.get("/llm/ollama/api/version")

        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["version"], str)
        assert body["version"]


class TestCaseEndToEndShow:
    """Cover ``POST /ollama/api/show``."""

    @pytest.fixture(scope="function")
    async def client(self, app, llm_component) -> t.AsyncIterator[Client]:
        component_ = llm_component

        class StubLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "stub"
            verbose_name = "Stub LLM"
            component = component_
            heartbeat_interval = 0
            serving = ("ollama",)

        app.models.add_model_resource("/llm/", StubLLMResource)

        async with Client(app=app) as client:
            yield client

    @pytest.mark.parametrize(
        ["body"],
        [
            pytest.param({"model": "stub"}, id="model_field"),
            pytest.param({"name": "stub"}, id="legacy_name_field"),
            pytest.param({"model": "other"}, id="model_mismatch_is_accepted"),
            pytest.param({}, id="empty_body"),
            pytest.param({"model": "stub", "verbose": True}, id="verbose_flag"),
        ],
    )
    async def test_returns_static_metadata_envelope(self, client: Client, body: dict[str, t.Any]) -> None:
        response = await client.post("/llm/ollama/api/show", json=body)

        assert response.status_code == 200, response.text
        envelope = response.json()
        assert set(envelope.keys()) == {"modelfile", "parameters", "template", "details", "model_info", "capabilities"}
        assert envelope["modelfile"] == ""
        assert envelope["parameters"] == ""
        assert envelope["template"] == ""
        assert envelope["details"]["family"] == "flama"
        assert envelope["details"]["format"] == "flama"
        assert "flama" in envelope["details"]["families"]
        assert envelope["model_info"]["general.architecture"] == "flama"
        assert "completion" in envelope["capabilities"]
        assert "tools" not in envelope["capabilities"]
        assert "vision" not in envelope["capabilities"]
        assert "audio" not in envelope["capabilities"]

    @pytest.mark.parametrize(
        ["capabilities", "expected_caps"],
        [
            pytest.param(
                LLMModelCapabilities(text=True),
                {"completion"},
                id="text_only",
            ),
            pytest.param(
                LLMModelCapabilities(text=True, tools=True),
                {"completion", "tools"},
                id="tools",
            ),
            pytest.param(
                LLMModelCapabilities(text=True, image=True),
                {"completion", "vision"},
                id="vision",
            ),
            pytest.param(
                LLMModelCapabilities(text=True, audio=True),
                {"completion", "audio"},
                id="audio",
            ),
            pytest.param(
                LLMModelCapabilities(text=True, image=True, audio=True, tools=True),
                {"completion", "tools", "vision", "audio"},
                id="all",
            ),
        ],
    )
    async def test_advertises_capabilities(
        self,
        client: Client,
        llm_component,
        capabilities: LLMModelCapabilities,
        expected_caps: set[str],
    ) -> None:
        with patch.object(llm_component.model.backend, "capabilities", capabilities):
            response = await client.post("/llm/ollama/api/show", json={"model": "stub"})

        assert response.status_code == 200, response.text
        envelope = response.json()
        assert set(envelope["capabilities"]) == expected_caps


class TestCaseEndToEndOpenAICompat:
    """Cover the OpenAI-compatible surface served under Ollama's prefix (Copilot-compat path).

    GitHub Copilot Chat (Ollama provider) targets ``POST /ollama/v1/chat/completions`` etc., so the
    Ollama serving layer composes :class:`OllamaOpenAICompatMixin` to re-mount the OpenAI handlers at
    those paths. This suite confirms the dispatch yields the OpenAI wire shape (JSON envelope or SSE
    chunks), not the Ollama dialect.
    """

    @pytest.fixture(scope="function")
    async def client(self, app, llm_component) -> t.AsyncIterator[Client]:
        component_ = llm_component

        class StubLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "stub"
            verbose_name = "Stub LLM"
            component = component_
            heartbeat_interval = 0
            serving = ("ollama",)

        app.models.add_model_resource("/llm/", StubLLMResource)

        async with Client(app=app) as client:
            yield client

    async def test_models_endpoint_returns_openai_envelope(self, client: Client) -> None:
        response = await client.get("/llm/ollama/v1/models")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["object"] == "list"
        assert isinstance(body["data"], list)
        assert body["data"][0]["id"] == "stub"
        assert body["data"][0]["object"] == "model"

    async def test_chat_completions_buffered_returns_openai_envelope(self, client: Client) -> None:
        response = await client.post(
            "/llm/ollama/v1/chat/completions",
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
        assert body["choices"][0]["message"]["role"] == "assistant"
        assert "usage" in body

    async def test_chat_completions_stream_emits_openai_chunks(self, client: Client) -> None:
        response = await client.post(
            "/llm/ollama/v1/chat/completions",
            json={
                "model": "stub",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

        assert response.status_code == 200, response.text
        assert "text/event-stream" in response.headers.get("content-type", "")
        text = response.text
        assert "chat.completion.chunk" in text
        assert "data: [DONE]" in text

    async def test_completions_buffered_returns_openai_envelope(self, client: Client) -> None:
        response = await client.post(
            "/llm/ollama/v1/completions",
            json={"model": "stub", "prompt": "hello", "stream": False},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["object"] == "text_completion"
        assert body["model"] == "stub"
        assert "choices" in body


class TestCaseOllamaServingParse:
    """Cover :meth:`OllamaServing.parse` translation from Ollama canonical wire to L2 Messages.

    These tests exercise the LLMServing façade with ``kind="messages"`` over a single-element list to
    pin down the dialect-specific Ollama content-part coverage; the symmetric tool-list façade and
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
                {
                    "role": "assistant",
                    "tool_calls": [{"function": {"name": "f", "arguments": {"q": "x"}}}],
                },
                (
                    AssistantMessage(
                        tool_calls=(ToolCall(function={"name": "f", "arguments": {"q": "x"}}),),
                    ),
                ),
                None,
                id="ollama_tool_call_without_id",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image:uri", "data": "QUFB", "format": "png"},
                    ],
                },
                (
                    UserMessage(
                        content=(
                            TextContent(text="describe"),
                            ImageURI(source=SourceURI(data="QUFB"), format="png"),
                        ),
                    ),
                ),
                None,
                id="text_and_image_uri",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "image:url", "url": "https://cdn.example/img.png"}]},
                (UserMessage(content=(ImageURL(source=SourceURL(url="https://cdn.example/img.png")),)),),
                None,
                id="image_url_canonical",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "audio:url", "url": "x"}]},
                None,
                (LLMUnsupportedContentPart, "Wrong content part type 'audio:url'"),
                id="unsupported_part_type",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "image:uri", "data": "x", "format": "tiff"}]},
                None,
                (ValueError, "Wrong image format"),
                id="invalid_image_format",
            ),
        ],
        indirect=["exception"],
    )
    def test_parse(self, value: dict[str, t.Any], expected: tuple[Message, ...] | None, exception) -> None:
        with exception:
            assert OllamaServing.parse([value], kind="messages") == expected
