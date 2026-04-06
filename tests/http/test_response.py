import json
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from flama import http, types


class TestCaseResponse:
    async def test_call(self):
        response = http.Response()
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.Response.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]

    def test_eq(self):
        assert http.Response(content="foo") == http.Response(content="foo")
        assert http.Response(content="foo") != http.Response(content="bar")

    def test_hash(self):
        assert hash(http.Response(content="foo")) == hash(http.Response(content="foo"))
        assert hash(http.Response(content="foo")) != hash(http.Response(content="bar"))


class TestCaseHTMLResponse:
    async def test_call(self):
        response = http.HTMLResponse()
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.HTMLResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCasePlainTextResponse:
    async def test_call(self):
        response = http.PlainTextResponse()
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.PlainTextResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCaseJSONResponse:
    @pytest.fixture
    def schema(self):
        return Mock()

    async def test_call(self):
        response = http.JSONResponse(content={})
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.JSONResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]

    @pytest.mark.parametrize(
        ["content", "result", "exception"],
        (
            pytest.param(
                {"foo": {"bar": [1, "foobar", 2.0, True, None]}},
                {"foo": {"bar": [1, "foobar", 2.0, True, None]}},
                None,
                id="default",
            ),
            pytest.param({"foo": Mock()}, None, TypeError, id="error"),
        ),
        indirect=["exception"],
    )
    def test_render(self, content, result, exception):
        with exception:
            response = http.JSONResponse(content=content)

            assert json.loads(response.body.decode()) == result


class TestCaseRedirectResponse:
    async def test_call(self):
        response = http.RedirectResponse(url="")
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.RedirectResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCaseStreamingResponse:
    async def test_call(self):
        response = http.StreamingResponse(content=(x for x in "foo"))
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.StreamingResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]


class TestCaseFileResponse:
    async def test_call(self):
        response = http.FileResponse(path="")
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.responses.FileResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]
