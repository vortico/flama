from unittest.mock import MagicMock, Mock, patch

import pytest

from flama import exceptions
from flama.models.models.tensorflow import Model


class TestCaseModel:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock()

    @pytest.mark.parametrize(
        ["np_installed", "tf_installed", "expected", "exception"],
        [
            pytest.param(True, True, [[0.0], [1.0], [1.0], [0.0]], None, id="success"),
            pytest.param(False, True, None, exceptions.FrameworkNotInstalled, id="numpy-not-installed"),
            pytest.param(True, False, None, exceptions.FrameworkNotInstalled, id="tensorflow-not-installed"),
        ],
    )
    def test_prediction(self, model, np_installed, tf_installed, expected, exception):
        mock_np = MagicMock()
        mock_np.array = MagicMock(return_value="np_array")
        model.predict = MagicMock(return_value=MagicMock(tolist=MagicMock(return_value=expected)))

        m = Model(model, MagicMock(), None)

        with (
            patch("flama.models.models.tensorflow.np", mock_np if np_installed else None),
            patch("flama.models.models.tensorflow.tf", MagicMock() if tf_installed else None),
        ):
            if exception is not None:
                with pytest.raises(exception):
                    m._prediction([[0, 0], [0, 1], [1, 0], [1, 1]])
            else:
                assert m._prediction([[0, 0], [0, 1], [1, 0], [1, 1]]) == expected
                mock_np.array.assert_called_once_with([[0, 0], [0, 1], [1, 0], [1, 1]])
                model.predict.assert_called_once_with("np_array")
