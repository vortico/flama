from io import BytesIO

import pytest
import tensorflow as tf
import torch
from pytest import param
from sklearn.linear_model import LogisticRegression

import flama


class TestCaseSerialize:
    @pytest.fixture
    def tensorflow_model(self):
        tf_model = tf.keras.models.Sequential(
            [
                tf.keras.layers.Flatten(input_shape=(28, 28)),
                tf.keras.layers.Dense(128, activation="relu"),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.Dense(10, activation="softmax"),
            ]
        )

        tf_model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])

        return tf_model

    @pytest.fixture
    def sklearn_model(self):
        return LogisticRegression()

    @pytest.fixture
    def pytorch_model(self):
        class Model(torch.nn.Module):
            def forward(self, x):
                return x + 10

        return Model()

    @pytest.fixture(scope="function")
    def model(self, request, tensorflow_model, sklearn_model, pytorch_model):
        if request.param == "tensorflow":
            return tensorflow_model

        if request.param == "sklearn":
            return sklearn_model

        if request.param == "pytorch":
            return pytorch_model

        raise ValueError("Unknown model")

    @pytest.mark.parametrize(
        ("lib", "model", "model_class"),
        (
            param(flama.ModelFormat.tensorflow, "tensorflow", tf.keras.models.Sequential, id="tensorflow"),
            param(flama.ModelFormat.sklearn, "sklearn", LogisticRegression, id="sklearn"),
            param(flama.ModelFormat.pytorch, "pytorch", torch.jit.RecursiveScriptModule, id="pytorch"),
        ),
        indirect=["model"],
    )
    def test_serialize_bytes(self, lib, model, model_class):
        model_binary = flama.dumps(lib, model)

        load_model = flama.loads(model_binary)

        assert load_model.lib == flama.ModelFormat(lib)
        assert isinstance(load_model.model, model_class)

    @pytest.mark.parametrize(
        ("lib", "model", "model_class"),
        (
            param(flama.ModelFormat.tensorflow, "tensorflow", tf.keras.models.Sequential, id="tensorflow"),
            param(flama.ModelFormat.sklearn, "sklearn", LogisticRegression, id="sklearn"),
            param(flama.ModelFormat.pytorch, "pytorch", torch.jit.RecursiveScriptModule, id="pytorch"),
        ),
        indirect=["model"],
    )
    def test_serialize_stream(self, lib, model, model_class):
        model_binary = BytesIO()
        flama.dump(lib, model, model_binary)

        model_binary.seek(0)

        load_model = flama.load(model_binary)

        assert load_model.lib == flama.ModelFormat(lib)
        assert isinstance(load_model.model, model_class)
