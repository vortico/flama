from unittest.mock import Mock

import pytest
from pytest import param

from flama.models import ModelComponent, ModelResource, ModelResourceType, PyTorchModel, SKLearnModel, TensorFlowModel


class TestCaseModelResource:
    @pytest.fixture(params=["tensorflow", "sklearn"])
    def model(self, request):
        if request.param == "pytorch":
            return PyTorchModel(Mock())
        elif request.param == "sklearn":
            return SKLearnModel(Mock())
        elif request.param == "tensorflow":
            return TensorFlowModel(Mock())
        else:
            raise AttributeError("Wrong lib")

    @pytest.fixture
    def component(self, model):
        class SpecificModelComponent(ModelComponent):
            def resolve(self) -> type(model):
                return self.model

        return SpecificModelComponent(model)

    @pytest.fixture
    def resource_using_component(self, component):
        component_ = component

        class PuppyModelResource(ModelResource, metaclass=ModelResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        return PuppyModelResource()

    @pytest.fixture(params=["tensorflow", "sklearn"])
    def resource_using_model_path(self, request):
        if request.param == "pytorch":
            model_path_ = "tests/models/pytorch_model.flm"
        elif request.param == "sklearn":
            model_path_ = "tests/models/sklearn_model.flm"
        elif request.param == "tensorflow":
            model_path_ = "tests/models/tensorflow_model.flm"
        else:
            raise AttributeError("Wrong lib")

        class PuppyModelResource(ModelResource, metaclass=ModelResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            model_path = model_path_

        return PuppyModelResource()

    def test_resource_using_component(self, resource_using_component, model, component):
        assert not hasattr(resource_using_component, "name")
        assert not hasattr(resource_using_component, "verbose_name")
        assert hasattr(resource_using_component, "component")
        assert resource_using_component.component == component
        assert hasattr(resource_using_component, "model")
        assert resource_using_component.model == model
        assert hasattr(resource_using_component, "_meta")
        assert resource_using_component._meta.name == "puppy"
        assert resource_using_component._meta.verbose_name == "Puppy"
        assert resource_using_component._meta.namespaces == {
            "model": {"component": component, "model": model, "model_type": component.get_model_type()}
        }

    def test_resource_using_model_path(self, resource_using_model_path):
        assert not hasattr(resource_using_model_path, "name")
        assert not hasattr(resource_using_model_path, "verbose_name")
        assert hasattr(resource_using_model_path, "component")
        component = resource_using_model_path.component
        assert hasattr(resource_using_model_path, "model")
        assert resource_using_model_path.model == component.model
        assert hasattr(resource_using_model_path, "_meta")
        assert resource_using_model_path._meta.name == "puppy"
        assert resource_using_model_path._meta.verbose_name == "Puppy"
        assert resource_using_model_path._meta.namespaces == {
            "model": {"component": component, "model": component.model, "model_type": component.get_model_type()}
        }


class TestCaseModelResourceMethods:
    @pytest.fixture(scope="function", autouse=True)
    def add_models(self, app):
        app.models.add_model("/pytorch/", model="tests/models/pytorch_model.flm", name="pytorch")
        app.models.add_model("/sklearn/", model="tests/models/sklearn_model.flm", name="sklearn")
        app.models.add_model("/tensorflow/", model="tests/models/tensorflow_model.flm", name="tensorflow")

    @pytest.mark.parametrize(
        ("url", "output"),
        (
            param(
                "/pytorch/",
                {"modules": ["RecursiveScriptModule(original_name=Model)"], "parameters": {}, "state": {}},
                id="pytorch",
            ),
            param(
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
            param(
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
    )
    def test_inspect(self, client, url, output):
        response = client.get(url)
        assert response.status_code == 200, response.json()
        assert response.json() == output

    @pytest.mark.parametrize(
        ("url", "x", "y"),
        (
            param(
                "/pytorch/predict/",
                [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]],
                [[10, 11, 12, 13, 14, 15, 16, 17, 18, 19]],
                id="pytorch",
            ),
            param(
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
                id="sklearn",
            ),
            param(
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
                id="tensorflow",
            ),
        ),
    )
    def test_predict(self, client, url, x, y):
        response = client.post(url, json={"input": x})
        assert response.status_code == 200, response.json()
        for a, e in zip(response.json()["output"], y):
            assert a == pytest.approx(e)
