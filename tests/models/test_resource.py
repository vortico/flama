from unittest.mock import Mock

import pytest

from flama.models import ModelComponent, ModelResource, ModelResourceType, PyTorchModel, SKLearnModel, TensorFlowModel
from flama.resources.exceptions import ResourceAttributeError


class TestCaseModelResource:
    @pytest.fixture(params=["tensorflow", "sklearn", "torch"])
    def model(self, request):
        return {"sklearn": SKLearnModel(Mock()), "tensorflow": TensorFlowModel(Mock()), "torch": PyTorchModel(Mock())}[
            request.param
        ]

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
        ("lib", "model_path", "url", "output"),
        (
            pytest.param(
                "torch",
                "torch",
                "/torch/",
                {"modules": ["RecursiveScriptModule(original_name=Model)"], "parameters": {}, "state": {}},
                id="torch",
            ),
            pytest.param(
                "sklearn",
                "sklearn",
                "/sklearn/",
                {
                    "C": 1.0,
                    "class_weight": None,
                    "dual": False,
                    "fit_intercept": True,
                    "intercept_scaling": 1,
                    "l1_ratio": None,
                    "max_iter": 100,
                    "multi_class": "auto",
                    "n_jobs": None,
                    "penalty": "l2",
                    "random_state": None,
                    "solver": "lbfgs",
                    "tol": 0.0001,
                    "verbose": 0,
                    "warm_start": False,
                },
                id="sklearn",
            ),
            pytest.param(
                "tensorflow",
                "tensorflow",
                "/tensorflow/",
                {
                    "class_name": "Sequential",
                    "config": {
                        "name": "sequential_1",
                        "layers": [
                            {
                                "class_name": "InputLayer",
                                "config": {
                                    "batch_input_shape": [None, 1],
                                    "dtype": "float32",
                                    "sparse": False,
                                    "ragged": False,
                                    "name": "dense_3_input",
                                },
                            },
                            {
                                "class_name": "Dense",
                                "config": {
                                    "name": "dense_3",
                                    "trainable": True,
                                    "batch_input_shape": [None, 1],
                                    "dtype": "float32",
                                    "units": 200,
                                    "activation": "linear",
                                    "use_bias": True,
                                    "kernel_initializer": {"class_name": "GlorotUniform", "config": {"seed": None}},
                                    "bias_initializer": {"class_name": "Zeros", "config": {}},
                                    "kernel_regularizer": None,
                                    "bias_regularizer": None,
                                    "activity_regularizer": None,
                                    "kernel_constraint": None,
                                    "bias_constraint": None,
                                },
                            },
                            {
                                "class_name": "Activation",
                                "config": {
                                    "name": "activation_2",
                                    "trainable": True,
                                    "dtype": "float32",
                                    "activation": "relu",
                                },
                            },
                            {
                                "class_name": "Dense",
                                "config": {
                                    "name": "dense_4",
                                    "trainable": True,
                                    "dtype": "float32",
                                    "units": 45,
                                    "activation": "linear",
                                    "use_bias": True,
                                    "kernel_initializer": {"class_name": "GlorotUniform", "config": {"seed": None}},
                                    "bias_initializer": {"class_name": "Zeros", "config": {}},
                                    "kernel_regularizer": None,
                                    "bias_regularizer": None,
                                    "activity_regularizer": None,
                                    "kernel_constraint": None,
                                    "bias_constraint": None,
                                },
                            },
                            {
                                "class_name": "Activation",
                                "config": {
                                    "name": "activation_3",
                                    "trainable": True,
                                    "dtype": "float32",
                                    "activation": "relu",
                                },
                            },
                            {
                                "class_name": "Dense",
                                "config": {
                                    "name": "dense_5",
                                    "trainable": True,
                                    "dtype": "float32",
                                    "units": 1,
                                    "activation": "linear",
                                    "use_bias": True,
                                    "kernel_initializer": {"class_name": "GlorotUniform", "config": {"seed": None}},
                                    "bias_initializer": {"class_name": "Zeros", "config": {}},
                                    "kernel_regularizer": None,
                                    "bias_regularizer": None,
                                    "activity_regularizer": None,
                                    "kernel_constraint": None,
                                    "bias_constraint": None,
                                },
                            },
                        ],
                    },
                    "keras_version": "2.10.0",
                    "backend": "tensorflow",
                },
                id="tensorflow",
            ),
        ),
        indirect=["model_path"],
    )
    def test_inspect(self, app, client, lib, model_path, url, output):
        app.models.add_model(f"/{lib}/", model=model_path, name=lib)

        response = client.get(url)
        assert response.status_code == 200, response.json()
        assert response.json() == output

    @pytest.mark.parametrize(
        ("lib", "model_path", "url", "x", "y", "status_code"),
        (
            pytest.param(
                "torch",
                "torch",
                "/torch/predict/",
                [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]],
                [[10, 11, 12, 13, 14, 15, 16, 17, 18, 19]],
                200,
                id="torch-200",
            ),
            pytest.param(
                "torch",
                "torch",
                "/torch/predict/",
                [["wrong"]],
                {"detail": "too many dimensions 'str'", "error": "HTTPException", "status_code": 400},
                400,
                id="torch-400",
            ),
            pytest.param(
                "sklearn",
                "sklearn",
                "/sklearn/predict/",
                [
                    [550.0, 2.3, 4.0],
                    [620.0, 3.3, 2.0],
                    [670.0, 3.3, 6.0],
                    [680.0, 3.9, 4.0],
                    [610.0, 2.7, 3.0],
                    [610.0, 3.0, 1.0],
                    [650.0, 3.7, 6.0],
                    [690.0, 3.7, 5.0],
                    [540.0, 2.7, 2.0],
                    [660.0, 3.3, 5.0],
                ],
                [0, 0, 1, 1, 0, 0, 1, 1, 0, 1],
                200,
                id="sklearn-200",
            ),
            pytest.param(
                "sklearn",
                "sklearn",
                "/sklearn/predict/",
                [["wrong"]],
                {
                    "detail": "dtype='numeric' is not compatible with arrays of bytes/strings.Convert your data to "
                    "numeric values explicitly instead.",
                    "error": "HTTPException",
                    "status_code": 400,
                },
                400,
                id="sklearn-400",
            ),
            pytest.param(
                "tensorflow",
                "tensorflow",
                "/tensorflow/predict/",
                [
                    [0.0],
                    [0.1111111111111111],
                    [0.2222222222222222],
                    [0.3333333333333333],
                    [0.4444444444444444],
                    [0.5555555555555556],
                    [0.6666666666666666],
                    [0.7777777777777777],
                    [0.8888888888888888],
                    [1.0],
                ],
                [
                    [-0.18502992391586304],
                    [-0.19394135475158691],
                    [-0.21624590456485748],
                    [-0.23871256411075592],
                    [-0.25075840950012207],
                    [-0.21501532196998596],
                    [-0.038977280259132385],
                    [0.13738776743412018],
                    [0.31375277042388916],
                    [0.4901178479194641],
                ],
                200,
                id="tensorflow-200",
            ),
            pytest.param(
                "tensorflow",
                "tensorflow",
                "/tensorflow/predict/",
                [["wrong"]],
                {"detail": "Bad Request", "error": "HTTPException", "status_code": 400},
                400,
                id="tensorflow-400",
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
                assert a == pytest.approx(e)
        else:
            assert response.json() == y
