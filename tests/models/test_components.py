import pytest
import tensorflow as tf
from pytest import param
from sklearn.linear_model import LogisticRegression

import flama
from flama.models.components import Model, ModelComponentBuilder


class TestCaseModelComponent:
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
    def tensorflow_dump(self, tensorflow_model):
        return flama.dumps("tensorflow", tensorflow_model)

    @pytest.fixture
    def sklearn_dump(self, sklearn_model):
        return flama.dumps("sklearn", sklearn_model)

    @pytest.fixture(scope="function")
    def model(self, request, sklearn_model, tensorflow_model):
        if request.param == "tensorflow":
            return tensorflow_model

        if request.param == "sklearn":
            return sklearn_model

        raise ValueError("Unknown model")

    @pytest.fixture(scope="function")
    def dump(self, request, sklearn_dump, tensorflow_dump):
        if request.param == "tensorflow":
            return tensorflow_dump

        if request.param == "sklearn":
            return sklearn_dump

        raise ValueError("Unknown model")

    @pytest.mark.parametrize(
        ("dump", "model"), (param("tensorflow", "tensorflow"), param("sklearn", "sklearn")), indirect=["dump", "model"]
    )
    def test_build(self, dump, model):
        component = ModelComponentBuilder.loads(dump)
        model_wrapper = component.model
        model_instance = model_wrapper.model
        assert isinstance(model_wrapper, Model)
        assert isinstance(model_instance, model.__class__)
