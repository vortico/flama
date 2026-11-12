from unittest.mock import MagicMock, Mock, call, patch

import pytest

from flama import exceptions
from flama.models.engine.backend.ml.transformers import TransformersBackend
from tests._utils import missing


class TestCaseTransformersBackend:
    @pytest.fixture(scope="function")
    def model(self):
        return Mock(return_value=[{"label": "POSITIVE", "score": 0.99}])

    @pytest.mark.parametrize(
        ["transformers_installed", "exception"],
        [
            pytest.param(True, None, id="success"),
            pytest.param(False, exceptions.DependencyNotInstalled, id="not_installed"),
        ],
        indirect=["exception"],
    )
    def test_predict(self, model, transformers_installed, exception):
        backend = TransformersBackend(model)
        x = [["hello"]]

        with (
            patch(
                "flama.models.engine.backend.ml.transformers.transformers",
                MagicMock() if transformers_installed else missing("transformers"),
            ),
            exception,
        ):
            assert backend.predict(x) == [{"label": "POSITIVE", "score": 0.99}]
            assert model.call_args_list == [call(x)]
