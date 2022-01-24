import sys
from unittest.mock import MagicMock, call, patch

import pytest
from starlette.testclient import TestClient

from flama import Flama


class TestCaseFlama:
    @pytest.fixture
    def lifespan(self):
        return MagicMock()

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    def test_lifespan(self, lifespan):
        with patch("flama.applications.Lifespan", new=lifespan):
            app = Flama()

            with TestClient(app):
                ...

            assert lifespan.call_args_list == [call(app, None)]
            assert lifespan()().__aenter__.call_args_list == [call()]
            assert lifespan()().__aexit__.call_args_list == [call(None, None, None)]

    @pytest.mark.skipif(
        sys.version_info < (3, 8), reason="requires python3.8 or higher to use async mocks"
    )  # PORT: Remove when stop supporting 3.7
    def test_lifespan_chain(self, lifespan):
        app = Flama(lifespan=lifespan)

        with TestClient(app):
            ...

        assert lifespan.__aenter__.call_args_list == [call()]
        assert lifespan.__aexit__.call_args_list == [call(None, None, None)]
