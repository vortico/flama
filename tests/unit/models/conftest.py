import typing as t
from unittest.mock import Mock

import pytest

from flama import Flama
from flama.injection import Parameter
from flama.models import ModelComponent
from flama.models.base import BaseLLMModel
from flama.models.models.pytorch import Model as PyTorchModel
from flama.models.models.sklearn import Model as SKLearnModel
from flama.models.models.tensorflow import Model as TensorFlowModel


class _StubLLMModel(BaseLLMModel):
    """Deterministic LLM stub used by integration tests.

    Overrides :meth:`_tokens` so callers don't need a real engine and can drive HTTP-level assertions with a known
    output, regardless of any vllm/mlx_lm dependency.
    """

    async def _tokens(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[str]:
        for token in prompt.split():
            yield token


@pytest.fixture(scope="function")
def app():
    return Flama(schema=None, docs=None)


@pytest.fixture(
    scope="function",
    params=[
        pytest.param("tensorflow", id="tensorflow"),
        pytest.param("sklearn", id="sklearn"),
        pytest.param("torch", id="torch"),
    ],
)
def model(request):
    return {
        "sklearn": SKLearnModel(Mock(), Mock(), Mock()),
        "tensorflow": TensorFlowModel(Mock(), Mock(), Mock()),
        "torch": PyTorchModel(Mock(), Mock(), Mock()),
    }[request.param]


@pytest.fixture(scope="function")
def component(model):
    class SpecificModelComponent(ModelComponent):
        def can_handle_parameter(self, parameter: Parameter) -> bool:
            return parameter.annotation == type(model)

    return SpecificModelComponent(model)


@pytest.fixture(scope="function")
def llm_model():
    meta = Mock()
    meta.to_dict.return_value = {
        "id": "stub-id",
        "timestamp": "2024-01-01T00:00:00Z",
        "model": {"obj": None, "info": None, "params": {}, "metrics": {}},
        "framework": {"lib": "stub", "version": "0.0.0", "config": None},
        "extra": {},
    }
    return _StubLLMModel(object(), meta, None)


@pytest.fixture(scope="function")
def llm_component(llm_model):
    class SpecificModelComponent(ModelComponent):
        def can_handle_parameter(self, parameter: Parameter) -> bool:
            return parameter.annotation == type(llm_model)

    return SpecificModelComponent(llm_model)
