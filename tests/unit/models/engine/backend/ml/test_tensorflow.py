from unittest.mock import MagicMock, Mock, call, patch

import pytest

from flama import exceptions
from flama.models.engine.backend.ml.tensorflow import TensorflowBackend


class TestCaseTensorflowBackend:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock()

    @pytest.mark.parametrize(
        ["np_installed", "tf_installed", "expected", "exception"],
        [
            pytest.param(True, True, [[0.0], [1.0], [1.0], [0.0]], None, id="success"),
            pytest.param(False, True, None, exceptions.FrameworkNotInstalled, id="numpy_not_installed"),
            pytest.param(True, False, None, exceptions.FrameworkNotInstalled, id="tensorflow_not_installed"),
        ],
        indirect=["exception"],
    )
    def test_predict(self, model, np_installed, tf_installed, expected, exception):
        mock_np = MagicMock()
        mock_np.array = MagicMock(return_value="np_array")
        model.predict = MagicMock(return_value=MagicMock(tolist=MagicMock(return_value=expected)))

        backend = TensorflowBackend(model)

        with (
            patch("flama.models.engine.backend.ml.tensorflow.np", mock_np if np_installed else None),
            patch("flama.models.engine.backend.ml.tensorflow.tf", MagicMock() if tf_installed else None),
            exception,
        ):
            assert backend.predict([[0, 0], [0, 1], [1, 0], [1, 1]]) == expected
            assert mock_np.array.call_args_list == [call([[0, 0], [0, 1], [1, 0], [1, 1]])]
            assert model.predict.call_args_list == [call("np_array")]
