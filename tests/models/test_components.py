import pytest

from flama.models.components import ModelComponentBuilder, PyTorchModel, SKLearnModel, TensorFlowModel


class TestCaseModelComponent:
    @pytest.mark.parametrize(
        ("model_path", "component_model_class", "serialized_model_class"),
        (
            pytest.param("sklearn", SKLearnModel, "sklearn", id="sklearn"),
            pytest.param("tensorflow", TensorFlowModel, "tensorflow", id="tensorflow"),
            pytest.param("torch", PyTorchModel, "torch", id="torch"),
        ),
        indirect=["model_path", "serialized_model_class"],
    )
    def test_build(self, model_path, component_model_class, serialized_model_class):
        with open(model_path, "rb") as f:
            component = ModelComponentBuilder.loads(f.read())

        model = component.model
        model_instance = model.model
        assert isinstance(model, component_model_class)
        assert isinstance(model_instance, serialized_model_class)
