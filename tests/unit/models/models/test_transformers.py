from unittest.mock import MagicMock, Mock, patch

import pytest

from flama import exceptions
from flama.models.models.transformers import Model


class TestCaseModel:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock(return_value=[{"label": "POSITIVE", "score": 0.99}])

    @pytest.mark.parametrize(
        ["transformers_installed", "exception"],
        [
            pytest.param(True, None, id="success"),
            pytest.param(False, exceptions.FrameworkNotInstalled, id="not-installed"),
        ],
    )
    def test_prediction(self, model, transformers_installed, exception):
        m = Model(model, MagicMock(), None)
        x = [["hello"]]

        with patch("flama.models.models.transformers.transformers", MagicMock() if transformers_installed else None):
            if exception is not None:
                with pytest.raises(exception):
                    m._prediction(x)
            else:
                assert m._prediction(x) == [{"label": "POSITIVE", "score": 0.99}]
                model.assert_called_once_with(x)
