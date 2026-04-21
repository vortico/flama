import contextlib
import pathlib
import tempfile
from unittest.mock import patch

import pytest

import flama
from flama.client import Client
from flama.models import MLResource, MLResourceType
from flama.models.components import ModelComponent
from flama.resources.exceptions import ResourceAttributeError
from tests._utils import NotInstalled, model_factory


def _get_component(client):
    return next(c for c in client.app.injector.components if isinstance(c, ModelComponent))


async def _error_stream(self, input_iter):
    raise RuntimeError("boom")
    yield  # makes this an async generator


async def _empty_input():
    return
    yield  # makes this an async generator


class TestCaseMLResource:
    def test_resource_using_component(self, app, model, component):
        component_ = component

        @app.models.model_resource("/")
        class PuppyMLResource(MLResource, metaclass=MLResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        resource = PuppyMLResource()

        assert not hasattr(resource, "name")
        assert not hasattr(resource, "verbose_name")
        assert hasattr(resource, "component")
        assert resource.component == component
        assert hasattr(resource, "model")
        assert resource.model == model
        assert hasattr(resource, "_meta")
        assert resource._meta.name == "puppy"
        assert resource._meta.verbose_name == "Puppy"
        assert resource._meta.namespaces == {
            "model": {"component": component, "model": model, "model_type": component.get_model_type()}
        }

    @pytest.mark.parametrize(
        ["model_path"],
        (
            pytest.param("sklearn", id="sklearn"),
            pytest.param("sklearn-pipeline", id="sklearn-pipeline"),
            pytest.param("tensorflow", id="tensorflow"),
            pytest.param("torch", id="torch"),
            pytest.param("transformers", id="transformers"),
        ),
        indirect=["model_path"],
    )
    def test_resource_using_model_path(self, app, model_path):
        model_path_ = model_path

        class PuppyMLResource(MLResource, metaclass=MLResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            model_path = model_path_

        resource = PuppyMLResource()

        app.models.add_model_resource("/", resource)

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

            class PuppyMLResource(MLResource, metaclass=MLResourceType):
                name = "puppy"
                verbose_name = "Puppy"


class TestCaseMLResourceMethods:
    @pytest.fixture(scope="function")
    async def client(self, request, app):
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

            app.models.add_model("/model/", model=pathlib.Path(f.name), name=request.param)

            async with Client(app=app) as client:
                yield client

    @pytest.mark.parametrize(
        ["client"],
        (
            pytest.param("torch", id="torch"),
            pytest.param("sklearn", id="sklearn"),
            pytest.param("sklearn-pipeline", id="sklearn-pipeline"),
            pytest.param("tensorflow", id="tensorflow"),
            pytest.param("transformers", id="transformers"),
        ),
        indirect=["client"],
    )
    async def test_inspect(self, client):
        response = await client.get("/model/")
        assert response.status_code == 200, response.json()
        inspect = response.json()
        assert set(inspect.keys()) == {"meta", "artifacts"}
        meta = inspect["meta"]
        assert set(meta.keys()) == {"id", "timestamp", "model", "framework", "extra"}
        assert set(meta["model"].keys()) == {"obj", "info", "params", "metrics"}
        assert set(meta["framework"].keys()) == {"lib", "version", "config"}

    @pytest.mark.parametrize(
        ("client", "x", "y", "status_code"),
        (
            pytest.param("torch", [[0, 0], [0, 1], [1, 0], [1, 1]], [[0], [1], [1], [0]], 200, id="torch-200"),
            pytest.param("torch", [["wrong"]], None, 400, id="torch-400"),
            pytest.param("sklearn", [[0, 0], [0, 1], [1, 0], [1, 1]], [0, 1, 1, 0], 200, id="sklearn-200"),
            pytest.param("sklearn", [["wrong"]], None, 400, id="sklearn-400"),
            pytest.param(
                "sklearn-pipeline", [[0, 0], [0, 1], [1, 0], [1, 1]], [0, 1, 1, 0], 200, id="sklearn-pipeline-200"
            ),
            pytest.param("sklearn-pipeline", [["wrong"]], None, 400, id="sklearn-pipeline-400"),
            pytest.param(
                "tensorflow", [[0, 0], [0, 1], [1, 0], [1, 1]], [[0], [1], [1], [0]], 200, id="tensorflow-200"
            ),
            pytest.param("tensorflow", [["wrong"]], None, 400, id="tensorflow-400"),
            pytest.param("transformers", ["hello"], None, 200, id="transformers-200"),
            pytest.param("transformers", [{"bad": "input"}], None, 400, id="transformers-400"),
        ),
        indirect=["client"],
    )
    async def test_predict(self, client, x, y, status_code):
        response = await client.post("/model/predict/", json={"input": x})

        assert response.status_code == status_code, response.json()
        if status_code == 200 and y is not None:
            for a, e in zip(response.json()["output"], y):
                assert a == pytest.approx(e, abs=3e-1)
        elif status_code == 200:
            assert "output" in response.json()

    @pytest.mark.parametrize(
        ("client", "x", "mock_output"),
        (
            pytest.param("torch", "0,0", None, id="torch"),
            pytest.param("sklearn", "0,0", None, id="sklearn"),
            pytest.param("sklearn-pipeline", "0,0", None, id="sklearn-pipeline"),
            pytest.param("tensorflow", "0,0", None, id="tensorflow"),
            pytest.param("transformers", "hello", None, id="transformers"),
            pytest.param("sklearn", "0,0", [[0.1, 0.9], [0.5, 0.5]], id="with-output"),
            pytest.param("torch", "0,0", [], id="torch-empty"),
            pytest.param("sklearn", "0,0", [], id="sklearn-empty"),
            pytest.param("tensorflow", "0,0", [], id="tensorflow-empty"),
            pytest.param("transformers", "hello", [], id="transformers-empty"),
            pytest.param("transformers", "hello", "error", id="transformers-error"),
            pytest.param("transformers", "hello", "pipeline-error", id="transformers-pipeline-error"),
        ),
        indirect=["client"],
    )
    async def test_stream(self, client, x, mock_output):
        if mock_output == "error":
            component = _get_component(client)

            with patch.object(type(component.model), "stream", _error_stream):
                with pytest.raises(RuntimeError, match="boom"):
                    await client.post("/model/stream/", json={"input": x})
            return

        elif mock_output == "pipeline-error":
            component = _get_component(client)

            with patch.object(component.model, "model", side_effect=RuntimeError("pipeline fail")):
                response = await client.post("/model/stream/", json={"input": x})

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            return

        elif mock_output == []:
            component = _get_component(client)

            items = [item async for item in component.model.stream(_empty_input())]
            assert items == []
            return

        ctx = contextlib.nullcontext()
        if mock_output:
            component = _get_component(client)

            async def _mock_stream(self, input_iter):
                for item in mock_output:
                    yield item

            ctx = patch.object(type(component.model), "stream", _mock_stream)

        with ctx:
            response = await client.post("/model/stream/", json={"input": x})

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        if mock_output:
            for item in mock_output:
                assert str(item).replace(" ", "") in response.text
