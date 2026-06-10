import typing as t
import uuid
from unittest.mock import patch

import pytest

from flama import exceptions
from flama.client import Client
from flama.models import LLMResource, LLMResourceType
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.resources.serving.llm.native import NativeServing
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    AudioURI,
    AudioURL,
    ImageURI,
    ImageURL,
    Message,
    SourceURI,
    SourceURL,
    TextContent,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from tests._utils import requires_templates

SERVING = "native"


class TestCaseEndToEndStreaming:
    """Cover the POST-create + GET-stream end-to-end SSE flow against a stub LLM resource."""

    @pytest.mark.parametrize(
        ["stream_id_factory", "expected_status"],
        [
            pytest.param(lambda: str(uuid.uuid4()), 404, id="unknown_stream"),
            pytest.param(lambda: "not-a-uuid", 400, id="invalid_uuid"),
        ],
    )
    async def test_get_rejects_unknown_stream(
        self, client: Client, stream_id_factory: t.Callable[[], str], expected_status: int
    ) -> None:
        response = await client.get(f"/llm/stream/{stream_id_factory()}/")

        assert response.status_code == expected_status

    @requires_templates
    async def test_chat_html_renders_resolved_stream_url(self, client: Client) -> None:
        response = await client.get("/llm/chat/")

        assert response.status_code == 200, response.text
        assert 'streamUrl="/llm/stream/"' in response.text

    @pytest.mark.parametrize(
        ["structured_part", "expected_modality"],
        [
            pytest.param(
                {"type": "image:uri", "data": "abc", "format": "png"},
                "image",
                id="image_uri",
            ),
            pytest.param(
                {"type": "audio:uri", "data": "AAAA", "format": "wav"},
                "audio",
                id="audio_uri",
            ),
        ],
    )
    async def test_query_rejects_multimodal_on_text_only_backend(
        self, client: Client, structured_part: dict[str, t.Any], expected_modality: str
    ) -> None:
        response = await client.post(
            "/llm/query/",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "describe"},
                            structured_part,
                        ],
                    }
                ],
                "transport": "conversation",
            },
        )

        assert response.status_code == 400, response.text
        assert expected_modality in response.text.lower()

    async def test_reconnect_replay_skips_emitted(self, client: Client, llm_component) -> None:
        async def _mock_generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
            for token in ("hello ", "world"):
                yield EngineDelta(text=token)

        with patch.object(type(llm_component.model.backend), "generate", _mock_generate):
            create = await client.post("/llm/stream/", json={"prompt": "hi"})
            assert create.status_code == 200, create.text
            stream_id = create.json()["id"]

            full = await client.get(f"/llm/stream/{stream_id}/")
            assert full.status_code == 200
            full_text = full.text
            assert "event: message.start" in full_text
            assert "event: message.stop" in full_text

            resumed = await client.get(
                f"/llm/stream/{stream_id}/",
                headers={"Last-Event-ID": f"{stream_id}.1"},
            )
            assert resumed.status_code == 200
            assert "event: message.start" not in resumed.text
            assert "event: message.stop" in resumed.text

    async def test_create_stream_malformed_messages_returns_400(self, client: Client) -> None:
        """A wire-shape violation surfaced by :meth:`NativeServing.parse` during stream creation (here
        ``tool_call_id`` on a non-``tool`` role) releases the freshly-allocated buffer and is translated
        into an HTTP 400."""
        response = await client.post(
            "/llm/stream/",
            json={
                "messages": [{"role": "user", "content": "hi", "tool_call_id": "c1"}],
                "transport": "conversation",
            },
        )

        assert response.status_code == 400, response.text

    async def test_get_stream_wraps_in_heartbeat_when_interval_positive(
        self, client: Client, app, llm_component
    ) -> None:
        """With a positive ``heartbeat_interval`` the GET stream handler wraps the SSE iterator in the
        heartbeat keep-alive; the wrapped stream still replays the full lifecycle for a fast generation."""
        resource_cls = type(app.routes[0].resource)

        with patch.object(resource_cls, "heartbeat_interval", 60.0):
            create = await client.post("/llm/stream/", json={"prompt": "hi"})
            assert create.status_code == 200, create.text
            stream_id = create.json()["id"]

            full = await client.get(f"/llm/stream/{stream_id}/")

        assert full.status_code == 200
        assert "event: message.start" in full.text
        assert "event: message.stop" in full.text


class TestCaseEndToEndConfigure:
    """Cover ``PUT /`` (configure) — merging request params into the model's generation defaults."""

    async def test_updates_generation_params(self, client: Client) -> None:
        response = await client.put("/llm/", json={"params": {"temperature": 0.5}})

        assert response.status_code == 200, response.text
        assert response.json()["params"]["temperature"] == 0.5


class TestCaseEndToEndQuery:
    """Cover ``POST /query/`` (buffered query) — the success envelope and the error-propagation contract."""

    async def test_buffered_query_returns_envelope(self, client: Client) -> None:
        response = await client.post("/llm/query/", json={"prompt": "hi"})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["stop_reason"]
        assert isinstance(body["blocks"], list)

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(exceptions.FrameworkNotInstalled, id="framework_not_installed")],
        indirect=["exception"],
    )
    async def test_framework_not_installed_propagates(self, client: Client, llm_component, exception) -> None:
        """``FrameworkNotInstalled`` raised by ``model.query`` is re-raised verbatim (not downgraded to an
        HTTP 400 / 500) so the missing-runtime failure surfaces to the ASGI server unchanged."""

        async def _mock(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise exceptions.FrameworkNotInstalled("vllm or mlx-lm")

        with patch.object(type(llm_component.model), "query", _mock), exception:
            await client.post("/llm/query/", json={"prompt": "hi"})

    async def test_generic_exception_returns_500(self, client: Client, llm_component) -> None:
        """A non-domain exception raised by ``model.query`` is contained by the handler and surfaced as an
        HTTP 500 rather than propagating to the server."""

        async def _mock(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
            raise RuntimeError("kaboom")

        with patch.object(type(llm_component.model), "query", _mock):
            response = await client.post("/llm/query/", json={"prompt": "hi"})

        assert response.status_code == 500, response.text


class TestCaseUnboundResource:
    """Pin the contract that resources defined outside a ``ModelsModule`` start with no ``streams`` slot bound."""

    @pytest.fixture(scope="function")
    def resource_class(self, llm_component) -> type[LLMResource]:
        component_ = llm_component

        class UnboundLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "unbound"
            verbose_name = "Unbound LLM"
            component = component_
            heartbeat_interval = 0

        return UnboundLLMResource

    def test_resource_has_no_streams_by_default(self, resource_class: type[LLMResource]) -> None:
        assert not hasattr(resource_class, "_streams")

    def test_streams_property_raises_when_unbound(self, resource_class: type[LLMResource]) -> None:
        with pytest.raises(exceptions.ApplicationError, match="not wired through ModelsModule"):
            _ = resource_class().streams


class TestCaseNativeServingParse:
    """Cover :meth:`NativeServing.parse` translation from canonical Native wire to L2 Messages.

    These tests exercise the LLMServing façade with ``kind="messages"`` over a single-element list to
    pin down the dialect-specific content-part coverage; the symmetric tool-list façade and the
    cross-dialect delegation matrix are exercised in
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
                id="assistant_tool_calls",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image:url", "url": "https://cdn.example/img.png"},
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
                {"role": "user", "content": [{"type": "image:uri", "data": "QUFB", "format": "png"}]},
                (UserMessage(content=(ImageURI(source=SourceURI(data="QUFB"), format="png"),)),),
                None,
                id="image_uri",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "audio:url", "url": "https://cdn.example/a.wav"}]},
                (UserMessage(content=(AudioURL(source=SourceURL(url="https://cdn.example/a.wav")),)),),
                None,
                id="audio_url",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "audio:uri", "data": "AAAA", "format": "wav"}]},
                (UserMessage(content=(AudioURI(source=SourceURI(data="AAAA"), format="wav"),)),),
                None,
                id="audio_uri",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "video:url", "url": "x"}]},
                None,
                (LLMUnsupportedContentPart, "Wrong content part type 'video:url'"),
                id="unsupported_part_type",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "image:uri", "data": "x", "format": "tiff"}]},
                None,
                (ValueError, "Wrong image format"),
                id="invalid_image_format",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "audio:uri", "data": "x", "format": "aac"}]},
                None,
                (ValueError, "Wrong audio format"),
                id="invalid_audio_format",
            ),
        ],
        indirect=["exception"],
    )
    def test_parse(self, value: dict[str, t.Any], expected: tuple[Message, ...] | None, exception) -> None:
        with exception:
            assert NativeServing.parse([value], kind="messages") == expected
