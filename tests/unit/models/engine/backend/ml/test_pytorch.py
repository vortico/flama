from unittest.mock import MagicMock, Mock, call, patch

import pytest

from flama import exceptions
from flama.models.engine.backend.ml.pytorch import PytorchBackend


class TestCasePytorchBackend:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock()

    @pytest.mark.parametrize(
        ["torch_installed", "expected", "exception"],
        [
            pytest.param(True, [[0.0], [1.0]], None, id="success"),
            pytest.param(False, None, exceptions.FrameworkNotInstalled, id="not_installed"),
        ],
        indirect=["exception"],
    )
    def test_predict(self, model, torch_installed, expected, exception):
        if torch_installed:
            mock_torch = MagicMock()
            mock_torch.Tensor = MagicMock(return_value="tensor_input")
            model.return_value = MagicMock(tolist=MagicMock(return_value=expected))
            patched_torch = mock_torch
        else:
            patched_torch = None

        backend = PytorchBackend(model)

        with patch("flama.models.engine.backend.ml.pytorch.torch", patched_torch), exception:
            assert backend.predict([[0, 0], [0, 1]]) == expected
            assert mock_torch.Tensor.call_args_list == [call([[0, 0], [0, 1]])]
            assert model.call_args_list == [call("tensor_input")]
