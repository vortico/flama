import typing as t
from unittest.mock import patch

import pytest

from flama.client import Client
from flama.models import LLMResource, LLMResourceType, ModelComponent
from flama.resources import data_structures
from flama.resources.exceptions import (
    ResourceModelNotFound,
    ResourceServingLayerUnknown,
    ResourceServingMethodInvalidPrefix,
)


class TestCaseLLMResource:
    def test_resource_using_component(self, app, llm_model, llm_component):
        component_ = llm_component

        @app.models.model_resource("/")
        class PuppyLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        resource = PuppyLLMResource()

        assert not hasattr(resource, "name")
        assert not hasattr(resource, "verbose_name")
        assert hasattr(resource, "component")
        assert resource.component == llm_component
        assert hasattr(resource, "model")
        assert resource.model == llm_model
        assert hasattr(resource, "_meta")
        assert resource._meta.name == "puppy"
        assert resource._meta.verbose_name == "Puppy"
        assert resource._meta.namespaces == {
            "model": {"component": llm_component, "model": llm_model, "model_type": llm_component.get_model_type()}
        }

    def test_resource_wrong(self):
        with pytest.raises(ResourceModelNotFound):

            class PuppyLLMResource(LLMResource, metaclass=LLMResourceType):
                name = "puppy"
                verbose_name = "Puppy"


class TestCaseLLMResourceTypeBuildMethods:
    @pytest.fixture(scope="function")
    def namespace(self, llm_component) -> dict[str, t.Any]:
        meta = data_structures.Metadata()
        meta.name = "stub"
        meta.verbose_name = "Stub"
        meta.namespaces["model"] = {
            "component": llm_component,
            "model": llm_component.model,
            "model_type": llm_component.get_model_type(),
        }
        return {"_meta": meta}

    @pytest.mark.parametrize(
        ["serving", "expected_method_names", "exception"],
        [
            pytest.param(
                ("native",),
                {"inspect", "configure", "query", "create_stream", "get_stream", "chat"},
                None,
                id="native_explicit",
            ),
            pytest.param(
                ("openai",),
                {"openai_chat_completions", "openai_completions", "openai_responses", "openai_models"},
                None,
                id="openai_explicit",
            ),
            pytest.param(
                ("native", "openai"),
                {
                    "inspect",
                    "configure",
                    "query",
                    "create_stream",
                    "get_stream",
                    "chat",
                    "openai_chat_completions",
                    "openai_completions",
                    "openai_responses",
                    "openai_models",
                },
                None,
                id="native_and_openai",
            ),
            pytest.param(
                ("ollama",),
                {
                    "ollama_chat",
                    "ollama_generate",
                    "ollama_show",
                    "ollama_tags",
                    "ollama_version",
                    "ollama_chat_completions",
                    "ollama_completions",
                    "ollama_responses",
                    "ollama_models",
                },
                None,
                id="ollama_explicit",
            ),
            pytest.param(
                ("anthropic",),
                {"anthropic_messages", "anthropic_models"},
                None,
                id="anthropic_explicit",
            ),
            pytest.param(
                None,
                {
                    "inspect",
                    "configure",
                    "query",
                    "create_stream",
                    "get_stream",
                    "chat",
                    "openai_chat_completions",
                    "openai_completions",
                    "openai_responses",
                    "openai_models",
                    "ollama_chat",
                    "ollama_generate",
                    "ollama_show",
                    "ollama_tags",
                    "ollama_version",
                    "ollama_chat_completions",
                    "ollama_completions",
                    "ollama_responses",
                    "ollama_models",
                    "anthropic_messages",
                    "anthropic_models",
                },
                None,
                id="default",
            ),
            pytest.param(
                ("native", "bogus"),
                None,
                (ResourceServingLayerUnknown, "unknown serving layer(s)"),
                id="rejects_unknown_layer",
            ),
        ],
        indirect=["exception"],
    )
    def test_build_methods(
        self,
        namespace: dict[str, t.Any],
        serving: tuple | None,
        expected_method_names: set[str] | None,
        exception,
    ) -> None:
        if serving is not None:
            namespace["serving"] = serving
        namespace["__qualname__"] = "PuppyLLMResource"

        with exception:
            result = LLMResourceType._build_methods(namespace)
            public_keys = {k for k in result if not k.startswith("_")}
            assert public_keys == expected_method_names

    def test_build_methods_rejects_bad_prefix(self, namespace: dict[str, t.Any]) -> None:
        """A non-native serving layer that declares a method without the ``<NAME>_`` prefix raises."""
        original = LLMResourceType.SERVING_METHODS

        class _BadServing:
            NAME = "openai"
            METHODS = ("chat",)  # missing "openai_" prefix

        LLMResourceType.SERVING_METHODS = {**original, "openai": _BadServing.METHODS}
        try:
            namespace["serving"] = ("openai",)
            namespace["__qualname__"] = "PuppyLLMResource"

            with pytest.raises(ResourceServingMethodInvalidPrefix, match="without the required prefix"):
                LLMResourceType._build_methods(namespace)
        finally:
            LLMResourceType.SERVING_METHODS = original

    def test_build_methods_combines_explicit_methods_with_serving(self, namespace: dict[str, t.Any]) -> None:
        """Explicit ``methods=`` passed by a downstream metaclass is merged on top of the serving set."""
        namespace["serving"] = ("native",)
        namespace["__qualname__"] = "PuppyLLMResource"

        def _add_extra(**kwargs):
            async def extra(self):  # pragma: no cover - body never executed in this test
                return None

            return {"_extra": extra}

        with patch.object(LLMResourceType, "_add_extra", staticmethod(_add_extra), create=True):
            result = LLMResourceType._build_methods(namespace, methods=("extra",))

            public_keys = {k for k in result if not k.startswith("_")}
            assert "extra" in public_keys
            assert {"inspect", "configure", "query", "create_stream", "get_stream", "chat"} <= public_keys


class TestCaseLLMResourceMethods:
    @pytest.fixture(scope="function")
    async def client(self, request, app, llm_component):
        if request.param == "stub":
            component_ = llm_component

            class StubLLMResource(LLMResource, metaclass=LLMResourceType):
                name = "stub"
                verbose_name = "Stub LLM"
                component = component_

            app.models.add_model_resource("/llm/", StubLLMResource)

            async with Client(app=app) as client:
                yield client
            return

        pytest.skip(f"Live LLM client case '{request.param}' is integration-only.")

    @staticmethod
    def _get_component(client) -> ModelComponent:
        return next(c for c in client.app.injector.components if isinstance(c, ModelComponent))

    @pytest.mark.parametrize(
        ["client"],
        [
            pytest.param("stub", id="stub"),
            pytest.param("vllm", id="vllm"),
        ],
        indirect=["client"],
    )
    async def test_inspect(self, client):
        response = await client.get("/llm/")

        assert response.status_code == 200, response.json()
        inspect_data = response.json()
        assert set(inspect_data.keys()) == {"meta", "manifest"}
        meta = inspect_data["meta"]
        assert set(meta.keys()) == {"id", "timestamp", "model", "framework", "extra"}
        assert set(meta["model"].keys()) == {"obj", "info", "params", "metrics"}
        assert set(meta["framework"].keys()) == {"family", "lib", "version", "config"}

    @pytest.mark.parametrize(
        ["client", "params"],
        [
            pytest.param("stub", {"temperature": 0.9, "max_tokens": 256}, id="stub"),
            pytest.param("vllm", {"temperature": 0.9, "max_tokens": 256}, id="vllm"),
        ],
        indirect=["client"],
    )
    async def test_configure(self, client, params):
        response = await client.put("/llm/", json={"params": params})

        assert response.status_code == 200
        data = response.json()
        assert "params" in data
        assert data["params"] == params

    @pytest.mark.parametrize(
        ["client", "body", "expected_status"],
        [
            pytest.param("stub", {"prompt": "hello world"}, 200, id="stub"),
            pytest.param("stub", {"prompt": "hello world", "params": {"temperature": 0.5}}, 200, id="stub_with_params"),
            pytest.param("stub", {"transport": "raw", "prompt": "hello world"}, 200, id="stub_raw"),
            pytest.param("stub", {"transport": "chat", "prompt": "hello world"}, 200, id="stub_chat"),
            pytest.param(
                "stub",
                {"transport": "chat", "prompt": "hello", "system": "be brief"},
                200,
                id="stub_chat_system",
            ),
            pytest.param(
                "stub",
                {
                    "transport": "conversation",
                    "messages": [
                        {"role": "user", "content": "hello"},
                        {"role": "assistant", "content": "hi"},
                        {"role": "user", "content": "world"},
                    ],
                },
                200,
                id="stub_conversation",
            ),
            pytest.param(
                "stub",
                {"transport": "raw", "prompt": "x", "system": "boom"},
                400,
                id="stub_raw_with_system_rejected",
            ),
            pytest.param(
                "stub",
                {"transport": "conversation", "messages": []},
                400,
                id="stub_empty_conversation_rejected",
            ),
            pytest.param("vllm", {"prompt": "What is Python?"}, 200, id="vllm"),
            pytest.param(
                "vllm", {"prompt": "What is Python?", "params": {"temperature": 0.5}}, 200, id="vllm_with_params"
            ),
        ],
        indirect=["client"],
    )
    async def test_query(self, client, body: dict[str, t.Any], expected_status: int):
        response = await client.post("/llm/query/", json=body)

        assert response.status_code == expected_status, response.text
        if expected_status == 200:
            data = response.json()
            assert {"id", "created", "blocks", "stop_reason"} <= set(data.keys())
            assert isinstance(data["id"], str) and data["id"]
            assert isinstance(data["created"], int)
            assert isinstance(data["blocks"], list)
            assert len(data["blocks"]) > 0
            for block in data["blocks"]:
                assert {"type", "channel", "text"} <= set(block.keys())
                assert block["type"] == "text"
                assert isinstance(block["channel"], str)
                assert isinstance(block["text"], str)

    @pytest.mark.parametrize(
        ["client", "body", "tokens", "raises", "expected_status"],
        [
            pytest.param("stub", {"prompt": "hello world"}, None, None, 200, id="stub"),
            pytest.param("stub", {"prompt": "hello world"}, ["foo ", "bar"], None, 200, id="stub_with_output"),
            pytest.param("stub", {"prompt": "hello world"}, None, RuntimeError("boom"), 200, id="stub_error"),
            pytest.param("stub", {"transport": "raw", "prompt": "hello world"}, None, None, 200, id="stub_raw"),
            pytest.param(
                "stub",
                {"transport": "chat", "prompt": "hello", "system": "be brief"},
                None,
                None,
                200,
                id="stub_chat_system",
            ),
            pytest.param(
                "stub",
                {
                    "transport": "conversation",
                    "messages": [
                        {"role": "user", "content": "hello"},
                        {"role": "assistant", "content": "hi"},
                        {"role": "user", "content": "world"},
                    ],
                },
                None,
                None,
                200,
                id="stub_conversation",
            ),
            pytest.param(
                "stub",
                {"transport": "chat", "prompt": "x", "messages": [{"role": "user", "content": "x"}]},
                None,
                None,
                400,
                id="stub_illegal_chat_with_messages",
            ),
            pytest.param("vllm", {"prompt": "Hello"}, None, None, 200, id="vllm"),
        ],
        indirect=["client"],
    )
    async def test_stream(self, client, body, tokens, raises, expected_status):
        if expected_status != 200:
            response = await client.post("/llm/stream/", json=body)

            assert response.status_code == expected_status
            return

        async def _consume(stream_id: str) -> str:
            sse = await client.get(f"/llm/stream/{stream_id}/")
            assert sse.status_code == 200, sse.text
            assert "text/event-stream" in sse.headers.get("content-type", "")
            return sse.text

        if tokens is None and raises is None:
            response = await client.post("/llm/stream/", json=body)

            assert response.status_code == 200, response.text
            payload = response.json()
            assert isinstance(payload.get("id"), str) and payload["id"]
            text = await _consume(payload["id"])
            assert "event: message.start" in text
            assert "event: message.stop" in text
            return

        component = self._get_component(client)

        if tokens is not None:
            from flama.models.engine.llm.delta import EngineDelta

            async def _mock_generate(self, inputs, /, **params):
                for item in tokens:
                    yield EngineDelta(text=item)

            with patch.object(type(component.model.backend), "generate", _mock_generate):
                response = await client.post("/llm/stream/", json=body)
                assert response.status_code == 200
                payload = response.json()
                text = await _consume(payload["id"])

                assert "event: message.start" in text
                assert "event: block.start" in text
                assert "event: block.delta" in text
                assert "event: block.stop" in text
                assert "event: message.stop" in text
                for item in tokens:
                    assert item in text
            return

        async def _failing_generate(self, inputs, /, **params):
            raise raises
            yield  # pragma: no cover

        with patch.object(type(component.model.backend), "generate", _failing_generate):
            response = await client.post("/llm/stream/", json=body)
            assert response.status_code == 200
            payload = response.json()
            text = await _consume(payload["id"])
            assert "event: error" in text
            assert "event: message.stop" in text
