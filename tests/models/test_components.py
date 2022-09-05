import pytest
import tensorflow as tf
import torch.jit
from pytest import param
from sklearn.linear_model import LogisticRegression

from flama.models.components import ModelComponentBuilder, PyTorchModel, SKLearnModel, TensorFlowModel


class TestCaseModelComponent:
    @pytest.mark.parametrize(
        ("model_file", "component_model_class", "serialized_model_class"),
        (
            param("tests/models/pytorch_model.flm", PyTorchModel, torch.jit.RecursiveScriptModule, id="pytorch"),
            param("tests/models/sklearn_model.flm", SKLearnModel, LogisticRegression, id="sklearn"),
            param("tests/models/tensorflow_model.flm", TensorFlowModel, tf.keras.models.Sequential, id="tensorflow"),
        ),
    )
    def test_build(self, model_file, component_model_class, serialized_model_class):
        with open(model_file, "rb") as f:
            component = ModelComponentBuilder.loads(f.read())

        model = component.model
        model_instance = model.model
        assert isinstance(model, component_model_class)
        assert isinstance(model_instance, serialized_model_class)
