from unittest.mock import MagicMock, Mock, call, patch

import pytest

from flama import exceptions
from flama.models.engine.backend.ml.tensorflow import TensorflowBackend
from tests._utils import missing


class TestCaseTensorflowBackend:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock()

    @pytest.mark.parametrize(
        ["tf_installed", "expected", "exception"],
        [
            pytest.param(True, [[0.0], [1.0], [1.0], [0.0]], None, id="success"),
            pytest.param(False, None, exceptions.DependencyNotInstalled, id="tensorflow_not_installed"),
        ],
        indirect=["exception"],
    )
    def test_predict(self, model, tf_installed, expected, exception):
        mock_tf = MagicMock()
        mock_tf.convert_to_tensor = MagicMock(return_value="tensor")
        model.predict = MagicMock(return_value=MagicMock(tolist=MagicMock(return_value=expected)))

        backend = TensorflowBackend(model)

        with (
            patch(
                "flama.models.engine.backend.ml.tensorflow.tf",
                mock_tf if tf_installed else missing("tensorflow"),
            ),
            exception,
        ):
            assert backend.predict([[0, 0], [0, 1], [1, 0], [1, 1]]) == expected
            assert mock_tf.convert_to_tensor.call_args_list == [call([[0, 0], [0, 1], [1, 0], [1, 1]])]
            assert model.predict.call_args_list == [call("tensor")]
