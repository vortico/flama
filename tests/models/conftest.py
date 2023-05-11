from unittest.mock import Mock

import pytest

from flama.models import ModelComponent
from flama.models.models.pytorch import PyTorchModel
from flama.models.models.sklearn import SKLearnModel
from flama.models.models.tensorflow import TensorFlowModel


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
        def resolve(self) -> type(model):
            return self.model

    return SpecificModelComponent(model)
