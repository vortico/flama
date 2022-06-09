import pytest
import tensorflow as tf
from pytest import param
from sklearn.linear_model import LogisticRegression

from flama.models.components import Model, ModelComponentBuilder


class TestCaseModelComponent:
    @pytest.mark.parametrize(
        ("model_file", "model"),
        (
            param("tests/models/tensorflow_model.flm", tf.keras.models.Sequential, id="tensorflow"),
            param("tests/models/sklearn_model.flm", LogisticRegression, id="sklearn"),
        ),
    )
    def test_build(self, model_file, model):
        with open(model_file, "rb") as f:
            component = ModelComponentBuilder.loads(f.read())

        model_wrapper = component.model
        model_instance = model_wrapper.model
        assert isinstance(model_wrapper, Model)
        assert isinstance(model_instance, model)
