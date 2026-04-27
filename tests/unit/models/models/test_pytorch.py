from unittest.mock import MagicMock, Mock, patch

import pytest

from flama import exceptions
from flama.models.models.pytorch import Model


class TestCaseModel:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock()

    @pytest.mark.parametrize(
        ["torch_installed", "expected", "exception"],
        [
            pytest.param(True, [[0.0], [1.0]], None, id="success"),
            pytest.param(False, None, exceptions.FrameworkNotInstalled, id="not-installed"),
        ],
    )
    def test_prediction(self, model, torch_installed, expected, exception):
        if torch_installed:
            mock_torch = MagicMock()
            mock_torch.Tensor = MagicMock(return_value="tensor_input")
            model.return_value = MagicMock(tolist=MagicMock(return_value=expected))
            patched_torch = mock_torch
        else:
            patched_torch = None

        m = Model(model, MagicMock(), None)

        with patch("flama.models.models.pytorch.torch", patched_torch):
            if exception is not None:
                with pytest.raises(exception):
                    m._prediction([[0, 0], [0, 1]])
            else:
                assert m._prediction([[0, 0], [0, 1]]) == expected
                mock_torch.Tensor.assert_called_once_with([[0, 0], [0, 1]])
                model.assert_called_once_with("tensor_input")
