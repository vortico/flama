from unittest.mock import Mock

import pytest

from flama.models.base import BaseLLMModel
from flama.models.components import LLMModelComponentBuilder, MLModelComponentBuilder, ModelComponent
from flama.models.models.pytorch import Model as PyTorchModel
from flama.models.models.sklearn import Model as SKLearnModel
from flama.models.models.tensorflow import Model as TensorFlowModel
from flama.models.models.transformers import Model as TransformersModel


class TestCaseModelComponent:
    def test_resolve(self):
        sentinel = Mock()
        component = ModelComponent(sentinel)

        assert component.resolve() is sentinel


class TestCaseMLModelComponentBuilder:
    @pytest.mark.parametrize(
        ["model_path", "component_model_class", "serialized_model_class", "exception"],
        [
            pytest.param("sklearn", SKLearnModel, "sklearn", None, id="sklearn"),
            pytest.param("sklearn-pipeline", SKLearnModel, "sklearn-pipeline", None, id="sklearn-pipeline"),
            pytest.param("tensorflow", TensorFlowModel, "tensorflow", None, id="tensorflow"),
            pytest.param("torch", PyTorchModel, "torch", None, id="torch"),
            pytest.param("transformers", TransformersModel, "transformers", None, id="transformers"),
            pytest.param("vllm", None, "vllm", ValueError("Wrong lib 'vllm'"), id="wrong-lib"),
        ],
        indirect=["model_path", "serialized_model_class", "exception"],
    )
    def test_load(self, model_path, component_model_class, serialized_model_class, exception):
        with exception:
            component = MLModelComponentBuilder.load(model_path)

        if not exception:
            assert isinstance(component.model, component_model_class)
            assert isinstance(component.model.model, serialized_model_class)


class TestCaseLLMModelComponentBuilder:
    @pytest.mark.parametrize(
        ["model_path", "exception"],
        [
            pytest.param("vllm", None, id="vllm"),
            pytest.param("sklearn", ValueError("Wrong lib 'sklearn'"), id="wrong-lib"),
        ],
        indirect=["model_path", "exception"],
    )
    def test_load(self, model_path, exception):
        with exception:
            component = LLMModelComponentBuilder.load(model_path)

        if not exception:
            assert isinstance(component.model, BaseLLMModel)
