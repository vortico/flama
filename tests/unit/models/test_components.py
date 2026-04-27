from unittest.mock import Mock

import pytest

from flama.models.components import ModelComponent, ModelComponentBuilder
from flama.models.models.pytorch import Model as PyTorchModel
from flama.models.models.sklearn import Model as SKLearnModel
from flama.models.models.tensorflow import Model as TensorFlowModel
from flama.models.models.transformers import Model as TransformersModel
from flama.models.models.vllm import Model as VllmModel


class TestCaseModelComponent:
    def test_resolve(self):
        sentinel = Mock()
        component = ModelComponent(sentinel)

        assert component.resolve() is sentinel


class TestCaseModelComponentBuilder:
    @pytest.mark.parametrize(
        ["model_path", "component_model_class", "serialized_model_class"],
        [
            pytest.param("sklearn", SKLearnModel, "sklearn", id="sklearn"),
            pytest.param("sklearn-pipeline", SKLearnModel, "sklearn-pipeline", id="sklearn-pipeline"),
            pytest.param("tensorflow", TensorFlowModel, "tensorflow", id="tensorflow"),
            pytest.param("torch", PyTorchModel, "torch", id="torch"),
            pytest.param("transformers", TransformersModel, "transformers", id="transformers"),
            pytest.param("vllm", VllmModel, "vllm", id="vllm"),
        ],
        indirect=["model_path", "serialized_model_class"],
    )
    def test_build(self, model_path, component_model_class, serialized_model_class):
        component = ModelComponentBuilder.build(model_path)

        assert isinstance(component.model, component_model_class)
        assert isinstance(component.model.model, serialized_model_class)
