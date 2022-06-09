import pytest
import tensorflow as tf
from sklearn.linear_model import LogisticRegression

import flama


def tensorflow_model(
    sequential=tf.keras.models.Sequential(
        [
            tf.keras.layers.Flatten(input_shape=(28, 28)),
            tf.keras.layers.Dense(128, activation="relu"),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(10, activation="softmax"),
        ]
    )
):
    tf_model = sequential

    tf_model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])

    return tf_model


def sklearn_model():
    return LogisticRegression()


@pytest.fixture(scope="function")
def model(request):
    if request.param == "tensorflow":
        return tensorflow_model()

    if request.param == "sklearn":
        return sklearn_model()

    raise ValueError("Unknown model")


@pytest.fixture(scope="function")
def model_dump(request):
    if request.param == "tensorflow":
        return flama.dumps("tensorflow", tensorflow_model())

    if request.param == "sklearn":
        return flama.dumps("sklearn", sklearn_model())

    raise ValueError("Unknown model")
