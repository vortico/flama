from unittest.mock import Mock

import pytest

from flama import Flama
from flama.injection import Parameter
from flama.models import ModelComponent
from flama.models.models.pytorch import Model as PyTorchModel
from flama.models.models.sklearn import Model as SKLearnModel
from flama.models.models.tensorflow import Model as TensorFlowModel


@pytest.fixture(scope="function")
def app():
    return Flama(schema=None, docs=None)


@pytest.fixture(params=["tensorflow", "sklearn", "torch"])
def model(request):
    return {
        "sklearn": SKLearnModel(Mock(), Mock(), Mock()),
        "tensorflow": TensorFlowModel(Mock(), Mock(), Mock()),
        "torch": PyTorchModel(Mock(), Mock(), Mock()),
    }[request.param]


@pytest.fixture
def component(model):
    class SpecificModelComponent(ModelComponent):
        def can_handle_parameter(self, parameter: Parameter) -> bool:
            return parameter.annotation == type(model)

        def resolve(self):
            return self.model

    return SpecificModelComponent(model)
