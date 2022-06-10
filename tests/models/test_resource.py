import pytest
from pytest import param


class TestCaseModelResource:
    @pytest.fixture(scope="function", autouse=True)
    def add_models(self, app):
        app.models.add_model("/tensorflow/", model="tests/models/tensorflow_model.flm", name="tensorflow")
        app.models.add_model("/sklearn/", model="tests/models/sklearn_model.flm", name="sklearn")

    @pytest.mark.parametrize(
        ("url", "output"),
        (
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
                    "keras_version": "2.9.0",
                    "backend": "tensorflow",
                },
                id="tensorflow",
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
        ),
    )
    def test_predict(self, client, url, x, y):
        response = client.post(url, json={"input": x})
        assert response.status_code == 200, response.json()
        for a, e in zip(response.json()["output"], y):
            assert a == pytest.approx(e)
