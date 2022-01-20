from unittest.mock import MagicMock, call, patch

from starlette.testclient import TestClient

from flama import Flama
from flama.applications import Lifespan


class TestCaseFlama:
    def test_lifespan(self):
        with patch("flama.applications.Lifespan", spec=Lifespan) as lifespan_mock:
            app = Flama()

            with TestClient(app):
                ...

            assert lifespan_mock.call_args_list == [call(app, None)]
            assert lifespan_mock()().__aenter__.call_args_list == [call()]
            assert lifespan_mock()().__aexit__.call_args_list == [call(None, None, None)]

    def test_lifespan_chain(self):
        lifespan_mock = MagicMock()
        app = Flama(lifespan=lifespan_mock)

        with TestClient(app):
            ...

        assert lifespan_mock.__aenter__.call_args_list == [call()]
        assert lifespan_mock.__aexit__.call_args_list == [call(None, None, None)]
