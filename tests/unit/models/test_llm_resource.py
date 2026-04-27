import pathlib
import tempfile
import typing as t
from unittest.mock import patch

import pytest

import flama
from flama.client import Client
from flama.models import LLMResource, LLMResourceType, ModelComponent
from flama.resources.exceptions import ResourceAttributeError
from tests._utils import NotInstalled, model_factory


class TestCaseLLMResource:
    def test_resource_using_component(self, app, llm_model, llm_component):
        component_ = llm_component

        @app.models.llm_resource("/")
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

    @pytest.mark.parametrize(
        ["model_path"],
        [pytest.param("vllm", id="vllm")],
        indirect=["model_path"],
    )
    def test_resource_using_model_path(self, app, model_path):
        model_path_ = model_path

        class PuppyLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            model_path = model_path_

        resource = PuppyLLMResource()

        app.models.add_llm_resource("/", resource)

        assert not hasattr(resource, "name")
        assert not hasattr(resource, "verbose_name")
        assert hasattr(resource, "component")
        component = resource.component
        assert hasattr(resource, "model")
        assert resource.model == component.model
        assert hasattr(resource, "_meta")
        assert resource._meta.name == "puppy"
        assert resource._meta.verbose_name == "Puppy"
        assert resource._meta.namespaces == {
            "model": {"component": component, "model": component.model, "model_type": component.get_model_type()}
        }

    def test_resource_wrong(self):
        with pytest.raises(ResourceAttributeError):

            class PuppyLLMResource(LLMResource, metaclass=LLMResourceType):
                name = "puppy"
                verbose_name = "Puppy"


class TestCaseLLMResourceMethods:
    @pytest.fixture(scope="function")
    async def client(self, request, app, llm_component):
        if request.param == "stub":
            component_ = llm_component

            class StubLLMResource(LLMResource, metaclass=LLMResourceType):
                name = "stub"
                verbose_name = "Stub LLM"
                component = component_

            app.models.add_llm_resource("/llm/", StubLLMResource)

            async with Client(app=app) as client:
                yield client
            return

        try:
            model = model_factory.model(request.param)
            lib = model_factory.lib(request.param)
            artifacts = model_factory.artifacts(request.param)
            config = model_factory.config(request.param)
        except NotInstalled:
            pytest.skip(f"Lib for case '{request.param}' is not installed.")

        with tempfile.NamedTemporaryFile(suffix=".flm") as f:
            flama.dump(model, path=f.name, artifacts=artifacts, config=config, lib=lib)
            f.flush()

            app.models.add_llm("/llm/", model=pathlib.Path(f.name), name=request.param)

            async with Client(app=app) as client:
                yield client

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
        assert set(inspect_data.keys()) == {"meta", "artifacts"}
        meta = inspect_data["meta"]
        assert set(meta.keys()) == {"id", "timestamp", "model", "framework", "extra"}
        assert set(meta["model"].keys()) == {"obj", "info", "params", "metrics"}
        assert set(meta["framework"].keys()) == {"lib", "version", "config"}

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
        ["client", "prompt", "params"],
        [
            pytest.param("stub", "hello world", None, id="stub"),
            pytest.param("stub", "hello world", {"temperature": 0.5}, id="stub-with-params"),
            pytest.param("vllm", "What is Python?", None, id="vllm"),
            pytest.param("vllm", "What is Python?", {"temperature": 0.5}, id="vllm-with-params"),
        ],
        indirect=["client"],
    )
    async def test_query(self, client, prompt, params):
        body: dict[str, t.Any] = {"prompt": prompt}
        if params is not None:
            body["params"] = params

        response = await client.post("/llm/query/", json=body)

        assert response.status_code == 200, response.json()
        data = response.json()
        assert "output" in data
        assert isinstance(data["output"], str)
        assert len(data["output"]) > 0

    @pytest.mark.parametrize(
        ["client", "prompt", "tokens", "raises"],
        [
            pytest.param("stub", "hello world", None, None, id="stub"),
            pytest.param("stub", "hello world", ["foo ", "bar"], None, id="stub-with-output"),
            pytest.param("stub", "hello world", None, RuntimeError("boom"), id="stub-error"),
            pytest.param("vllm", "Hello", None, None, id="vllm"),
        ],
        indirect=["client"],
    )
    async def test_stream(self, client, prompt, tokens, raises):
        if tokens is None and raises is None:
            response = await client.post("/llm/stream/", json={"prompt": prompt})

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            return

        component = self._get_component(client)

        if tokens is not None:

            async def _mock_tokens(self, prompt, /, **params):
                for item in tokens:
                    yield item

            with patch.object(type(component.model), "_tokens", _mock_tokens):
                response = await client.post("/llm/stream/", json={"prompt": prompt})

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            for item in tokens:
                assert item in response.text
            return

        async def _failing_stream(self, prompt, /, **params):
            raise raises
            yield  # pragma: no cover

        with (
            patch.object(type(component.model), "stream", _failing_stream),
            pytest.raises(type(raises), match=str(raises)),
        ):
            await client.post("/llm/stream/", json={"prompt": prompt})
