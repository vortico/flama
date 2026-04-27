from unittest.mock import MagicMock, Mock, patch

import pytest

from flama import exceptions
from flama.models.models.sklearn import Model


class TestCaseModel:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock()

    @pytest.mark.parametrize(
        ["sklearn_installed", "expected", "exception"],
        [
            pytest.param(True, [0, 1, 1, 0], None, id="success"),
            pytest.param(False, None, exceptions.FrameworkNotInstalled, id="not-installed"),
        ],
    )
    def test_prediction(self, model, sklearn_installed, expected, exception):
        model.predict = MagicMock(return_value=MagicMock(tolist=MagicMock(return_value=expected)))
        patched_sklearn = MagicMock() if sklearn_installed else None

        m = Model(model, MagicMock(), None)

        with patch("flama.models.models.sklearn.sklearn", patched_sklearn):
            if exception is not None:
                with pytest.raises(exception):
                    m._prediction([[0, 0], [0, 1], [1, 0], [1, 1]])
            else:
                assert m._prediction([[0, 0], [0, 1], [1, 0], [1, 1]]) == expected
                model.predict.assert_called_once_with([[0, 0], [0, 1], [1, 0], [1, 1]])
