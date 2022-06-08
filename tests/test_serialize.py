import pytest
import tensorflow as tf
from pytest import param
from sklearn.linear_model import LogisticRegression

import flama
from flama.serialize import Format


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

    @pytest.fixture(scope="function")
    def model(self, request, tensorflow_model, sklearn_model):
        if request.param == "tensorflow":
            return tensorflow_model

        if request.param == "sklearn":
            return sklearn_model

        raise ValueError("Unknown model")

    @pytest.mark.parametrize(
        ("lib", "model"), (param("tensorflow", "tensorflow"), param("sklearn", "sklearn")), indirect=["model"]
    )
    def test_serialize(self, lib, model):
        model_binary = flama.dumps(lib, model)

        load_model = flama.loads(model_binary)

        assert load_model.lib == Format(lib)
        assert isinstance(load_model.model, model.__class__)
