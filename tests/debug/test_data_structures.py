import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from flama import http
from flama.applications import Flama
from flama.debug.data_structures import App, Environment, Error, ErrorContext, NotFoundContext, Request
from flama.routing import Mount, Route


@pytest.fixture
def http_request():
    return MagicMock()


class TestCaseRequest:
    def test_from_request(self, asgi_scope, asgi_receive, asgi_send):
        request = http.Request(asgi_scope, asgi_receive, asgi_send)

        result = dataclasses.asdict(Request.from_request(request))

        assert result == {
            "client": None,
            "cookies": {},
            "headers": {},
            "method": "GET",
            "params": {"path": {}, "query": {}},
            "path": "/",
        }


class TestCaseError:
    def test_from_exception(self):
        try:
            raise ValueError("Foo")
        except ValueError as e:
            result = dataclasses.asdict(Error.from_exception(e))

        traceback = result.pop("traceback", None)
        assert traceback
        assert len(traceback) == 1
        frame = traceback[0]
        code = frame.pop("code", None)
        assert code
        assert frame == {
            "filename": "tests/debug/test_data_structures.py",
            "function": "test_from_exception",
            "line": 36,
            "vendor": None,
        }
        assert result == {"description": "Foo", "error": "ValueError"}


class TestCaseEnvironment:
    def test_from_system(self):
        result = dataclasses.asdict(Environment.from_system())

        path = result.pop("path", None)
        assert path
        assert list(result.keys()) == ["platform", "python", "python_version"]


class TestCaseApp:
    def test_from_app(self):
        def foo_handler(): ...

        def bar_handler(): ...

        app = Flama(
            routes=[
                Route("/", foo_handler, name="foo"),
                Mount("/subapp/", routes=[Route("/", bar_handler, name="bar")], name="subapp"),
            ],
            schema=None,
            docs=None,
        )

        result = dataclasses.asdict(App.from_app(app))

        assert result == {
            "name": None,
            "path": "/",
            "endpoints": [
                {
                    "path": "/",
                    "endpoint": "foo_handler",
                    "module": "tests.debug.test_data_structures",
                    "file": "tests/debug/test_data_structures.py",
                    "line": 66,
                    "name": "foo",
                },
            ],
            "apps": [
                {
                    "name": "subapp",
                    "path": "/subapp/",
                    "apps": [],
                    "endpoints": [
                        {
                            "path": "/",
                            "module": "tests.debug.test_data_structures",
                            "file": "tests/debug/test_data_structures.py",
                            "line": 68,
                            "endpoint": "bar_handler",
                            "name": "bar",
                        }
                    ],
                },
            ],
        }


class TestCaseErrorContext:
    def test_build(self):
        request_mock = MagicMock(Request)
        environment_mock = MagicMock(Environment)
        error_mock = MagicMock(Error)

        with (
            patch.object(Request, "from_request", return_value=request_mock),
            patch.object(Environment, "from_system", return_value=environment_mock),
            patch.object(Error, "from_exception", return_value=error_mock),
        ):
            context = dataclasses.asdict(ErrorContext.build(MagicMock(), MagicMock()))

        assert context == {"request": request_mock, "environment": environment_mock, "error": error_mock}


class TestCaseNotFoundContext:
    def test_build(self):
        request_mock = MagicMock(Request)
        environment_mock = MagicMock(Environment)
        app_mock = MagicMock(App)

        with (
            patch.object(Request, "from_request", return_value=request_mock),
            patch.object(Environment, "from_system", return_value=environment_mock),
            patch.object(App, "from_app", return_value=app_mock),
        ):
            context = dataclasses.asdict(NotFoundContext.build(MagicMock(), MagicMock()))

        assert context == {"request": request_mock, "environment": environment_mock, "app": app_mock}
