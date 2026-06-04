from unittest.mock import MagicMock, Mock, call, patch

import pytest

from flama import exceptions
from flama.models.engine.backend.ml.sklearn import SklearnBackend


class TestCaseSklearnBackend:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock()

    @pytest.mark.parametrize(
        ["sklearn_installed", "expected", "exception"],
        [
            pytest.param(True, [0, 1, 1, 0], None, id="success"),
            pytest.param(False, None, exceptions.FrameworkNotInstalled, id="not_installed"),
        ],
        indirect=["exception"],
    )
    def test_predict(self, model, sklearn_installed, expected, exception):
        model.predict = MagicMock(return_value=MagicMock(tolist=MagicMock(return_value=expected)))
        backend = SklearnBackend(model)

        with (
            patch("flama.models.engine.backend.ml.sklearn.sklearn", MagicMock() if sklearn_installed else None),
            exception,
        ):
            assert backend.predict([[0, 0], [0, 1], [1, 0], [1, 1]]) == expected
            assert model.predict.call_args_list == [call([[0, 0], [0, 1], [1, 0], [1, 1]])]
