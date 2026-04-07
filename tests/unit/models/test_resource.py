import pathlib
import tempfile

import pytest

import flama
from flama.client import Client
from flama.models import ModelResource, ModelResourceType
from flama.resources.exceptions import ResourceAttributeError
from tests._utils import NotInstalled
from tests.conftest import model_factory


class TestCaseModelResource:
    def test_resource_using_component(self, app, model, component):
        component_ = component

        @app.models.model_resource("/")
        class PuppyModelResource(ModelResource, metaclass=ModelResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        resource = PuppyModelResource()

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
        ),
        indirect=["model_path"],
    )
    def test_resource_using_model_path(self, app, model_path):
        model_path_ = model_path

        class PuppyModelResource(ModelResource, metaclass=ModelResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            model_path = model_path_

        resource = PuppyModelResource()

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

            class PuppyModelResource(ModelResource, metaclass=ModelResourceType):
                name = "puppy"
                verbose_name = "Puppy"


class TestCaseModelResourceMethods:
    @pytest.fixture(scope="function")
    async def client(self, request, app):
        try:
            model = model_factory.model(request.param)
        except NotInstalled:
            pytest.skip(f"Lib for case '{request.param}' is not installed.")

        with tempfile.NamedTemporaryFile(suffix=".flm") as f:
            flama.dump(model, path=f.name)
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
        assert set(meta["framework"].keys()) == {"lib", "version"}

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
        ),
        indirect=["client"],
    )
    async def test_predict(self, client, x, y, status_code):
        response = await client.post("/model/predict/", json={"input": x})

        assert response.status_code == status_code, response.json()
        if status_code == 200:
            for a, e in zip(response.json()["output"], y):
                assert a == pytest.approx(e, abs=3e-1)
