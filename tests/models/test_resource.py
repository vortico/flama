from unittest.mock import Mock

import pytest

from flama.models import ModelComponent, ModelResource, ModelResourceType
from flama.models.models.pytorch import PyTorchModel
from flama.models.models.sklearn import SKLearnModel
from flama.models.models.tensorflow import TensorFlowModel
from flama.resources.exceptions import ResourceAttributeError


class TestCaseModelResource:
    @pytest.fixture(params=["tensorflow", "sklearn", "torch"])
    def model(self, request):
        return {
            "sklearn": SKLearnModel(Mock(), Mock()),
            "tensorflow": TensorFlowModel(Mock(), Mock()),
            "torch": PyTorchModel(Mock(), Mock()),
        }[request.param]

    @pytest.fixture
    def component(self, model):
        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> type(model):
                return self.model

        return SpecificModelComponent(model)

    def test_resource_using_component(self, app, model, component):
        component_ = component

        @app.models.model("/")
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
    @pytest.mark.parametrize(
        ("lib", "model_path", "url"),
        (
            pytest.param("torch", "torch", "/torch/", id="torch"),
            pytest.param("sklearn", "sklearn", "/sklearn/", id="sklearn"),
            pytest.param("tensorflow", "tensorflow", "/tensorflow/", id="tensorflow"),
        ),
        indirect=["model_path"],
    )
    def test_inspect(self, app, client, lib, model_path, url):
        app.models.add_model(f"/{lib}/", model=model_path, name=lib)

        response = client.get(url)
        assert response.status_code == 200, response.json()
        inspect = response.json()
        assert set(inspect.keys()) == {"id", "timestamp", "model", "framework", "extra"}
        assert set(inspect["model"].keys()) == {"obj", "info", "params", "metrics"}
        assert set(inspect["framework"].keys()) == {"lib", "version"}

    @pytest.mark.parametrize(
        ("lib", "model_path", "url", "x", "y", "status_code"),
        (
            pytest.param(
                "torch",
                "torch",
                "/torch/predict/",
                [[0, 0], [0, 1], [1, 0], [1, 1]],
                [[0], [1], [1], [0]],
                200,
                id="torch-200",
            ),
            pytest.param("torch", "torch", "/torch/predict/", [["wrong"]], None, 400, id="torch-400"),
            pytest.param(
                "sklearn",
                "sklearn",
                "/sklearn/predict/",
                [[0, 0], [0, 1], [1, 0], [1, 1]],
                [0, 1, 1, 0],
                200,
                id="sklearn-200",
            ),
            pytest.param("sklearn", "sklearn", "/sklearn/predict/", [["wrong"]], None, 400, id="sklearn-400"),
            pytest.param(
                "tensorflow",
                "tensorflow",
                "/tensorflow/predict/",
                [[0, 0], [0, 1], [1, 0], [1, 1]],
                [[0], [1], [1], [0]],
                200,
                id="tensorflow-200",
            ),
            pytest.param(
                "tensorflow", "tensorflow", "/tensorflow/predict/", [["wrong"]], None, 400, id="tensorflow-400"
            ),
        ),
        indirect=["model_path"],
    )
    def test_predict(self, app, client, lib, model_path, url, x, y, status_code):
        app.models.add_model(f"/{lib}/", model=model_path, name=lib)

        response = client.post(url, json={"input": x})

        assert response.status_code == status_code, response.json()
        if status_code == 200:
            for a, e in zip(response.json()["output"], y):
                assert a == pytest.approx(e, abs=3e-1)
