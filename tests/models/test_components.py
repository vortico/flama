import pytest

from flama.models.components import ModelComponentBuilder
from flama.models.models.pytorch import PyTorchModel
from flama.models.models.sklearn import SKLearnModel
from flama.models.models.tensorflow import TensorFlowModel


class TestCaseModelComponent:
    @pytest.mark.parametrize(
        ("model_path", "component_model_class", "serialized_model_class"),
        (
            pytest.param("sklearn", SKLearnModel, "sklearn", id="sklearn"),
            pytest.param("sklearn-pipeline", SKLearnModel, "sklearn-pipeline", id="sklearn-pipeline"),
            pytest.param("tensorflow", TensorFlowModel, "tensorflow", id="tensorflow"),
            pytest.param("torch", PyTorchModel, "torch", id="torch"),
        ),
        indirect=["model_path", "serialized_model_class"],
    )
    def test_build(self, model_path, component_model_class, serialized_model_class):
        component = ModelComponentBuilder.load(model_path)

        model = component.model
        model_instance = model.model
        assert isinstance(model, component_model_class)
        assert isinstance(model_instance, serialized_model_class)
