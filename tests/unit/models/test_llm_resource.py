import pathlib
import tempfile
import typing as t
from unittest.mock import Mock

import pytest

import flama
from flama.client import Client
from flama.injection import Parameter
from flama.models import LLMResource, LLMResourceType, ModelComponent
from flama.models.components import ModelComponentBuilder
from flama.resources.exceptions import ResourceAttributeError
from tests._utils import NotInstalled, model_factory
from tests.unit.models.conftest import _StubLLMModel


def _make_stub_llm_component() -> ModelComponent:
    meta = Mock()
    meta.to_dict.return_value = {
        "id": "stub-id",
        "timestamp": "2024-01-01T00:00:00Z",
        "model": {"obj": None, "info": None, "params": {}, "metrics": {}},
        "framework": {"lib": "stub", "version": "0.0.0", "config": None},
        "extra": {},
    }
    model = _StubLLMModel(object(), meta, None)

    class StubComponent(ModelComponent):
        def can_handle_parameter(self, parameter: Parameter) -> bool:
            return parameter.annotation == type(model)

    return StubComponent(model)


@pytest.fixture(scope="function")
def model_path(request):
    try:
        model = model_factory.model(request.param)
    except NotInstalled:
        pytest.skip(f"Lib for case '{request.param}' is not installed.")

    with tempfile.NamedTemporaryFile(suffix=".flm") as f:
        lib = model_factory.lib(request.param)
        flama.dump(model, path=f.name, config={"engine_params": {"max_model_len": 256}}, lib=lib)
        f.flush()
        yield pathlib.Path(f.name)


@pytest.fixture(scope="function")
def llm_component(request):
    try:
        model = model_factory.model(request.param)
    except NotInstalled:
        pytest.skip(f"Lib for case '{request.param}' is not installed.")

    with tempfile.NamedTemporaryFile(suffix=".flm") as f:
        lib = model_factory.lib(request.param)
        flama.dump(model, path=f.name, config={"engine_params": {"max_model_len": 256}}, lib=lib)
        f.flush()
        yield ModelComponentBuilder.load(f.name)


class TestCaseLLMResource:
    @pytest.mark.parametrize(
        ["llm_component"],
        (pytest.param("vllm", id="vllm"),),
        indirect=["llm_component"],
    )
    def test_resource_using_component(self, app, llm_component):
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
        assert resource.model == llm_component.model
        assert hasattr(resource, "_meta")
        assert resource._meta.name == "puppy"
        assert resource._meta.verbose_name == "Puppy"
        assert resource._meta.namespaces == {
            "model": {
                "component": llm_component,
                "model": llm_component.model,
                "model_type": llm_component.get_model_type(),
            }
        }

    @pytest.mark.parametrize(
        ["model_path"],
        (pytest.param("vllm", id="vllm"),),
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


class TestCaseLLMResourceEndpoints:
    @pytest.fixture(scope="function")
    async def client(self, request, app):
        if request.param == "stub":
            component_ = _make_stub_llm_component()

            class StubLLMResource(LLMResource, metaclass=LLMResourceType):
                name = "stub"
                verbose_name = "Stub LLM"
                component = component_

            app.models.add_llm_resource("/llm/", StubLLMResource)

            async with Client(app=app) as client:
                yield client
        else:
            try:
                model = model_factory.model(request.param)
            except NotInstalled:
                pytest.skip(f"Lib for case '{request.param}' is not installed.")

            with tempfile.NamedTemporaryFile(suffix=".flm") as f:
                lib = model_factory.lib(request.param)
                flama.dump(model, path=f.name, config={"engine_params": {"max_model_len": 256}}, lib=lib)
                f.flush()

                app.models.add_llm("/llm/", model=pathlib.Path(f.name), name=request.param)

                async with Client(app=app) as client:
                    yield client

    @pytest.mark.parametrize(
        ["client"],
        (
            pytest.param("stub", id="stub"),
            pytest.param("vllm", id="vllm"),
        ),
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
        ("client", "params"),
        (
            pytest.param("stub", {"temperature": 0.9, "max_tokens": 256}, id="stub"),
            pytest.param("vllm", {"temperature": 0.9, "max_tokens": 256}, id="vllm"),
        ),
        indirect=["client"],
    )
    async def test_configure(self, client, params):
        response = await client.put("/llm/", json={"params": params})
        assert response.status_code == 200
        data = response.json()
        assert "params" in data
        assert data["params"] == params

    @pytest.mark.parametrize(
        ("client", "prompt", "params"),
        (
            pytest.param("stub", "hello", {}, id="stub"),
            pytest.param("stub", "hello", {"temperature": 0.5}, id="stub-with-params"),
            pytest.param("vllm", "What is Python?", {}, id="vllm"),
            pytest.param("vllm", "What is Python?", {"temperature": 0.5}, id="vllm-with-params"),
        ),
        indirect=["client"],
    )
    async def test_query(self, client, prompt, params):
        body: dict[str, t.Any] = {"prompt": prompt}
        if params:
            body["params"] = params
        response = await client.post("/llm/query/", json=body)
        assert response.status_code == 200, response.json()
        data = response.json()
        assert "output" in data
        assert isinstance(data["output"], str)
        assert len(data["output"]) > 0

    @pytest.mark.parametrize(
        ("client", "prompt", "params"),
        (
            pytest.param("stub", "hello world", {}, id="stub"),
            pytest.param("stub", "hello world", {"temperature": 0.5}, id="stub-with-params"),
            pytest.param("vllm", "Hello", {}, id="vllm"),
            pytest.param("vllm", "Hello", {"temperature": 0.5}, id="vllm-with-params"),
        ),
        indirect=["client"],
    )
    async def test_stream(self, client, prompt, params):
        body: dict[str, t.Any] = {"prompt": prompt}
        if params:
            body["params"] = params
        response = await client.post("/llm/stream/", json=body)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert "data:" in response.text
