import json
from unittest.mock import Mock

import pytest

from flama.http.responses.json import JSONResponse


class TestCaseJSONResponse:
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
            response = JSONResponse(content)

            assert json.loads(response.body.decode()) == result

    def test_media_type(self):
        response = JSONResponse({})

        assert response.headers["content-type"] == "application/json"

    async def test_call(self, asgi_scope, asgi_receive, asgi_send):
        response = JSONResponse({"key": "value"})

        await response(asgi_scope, asgi_receive, asgi_send)

        body = asgi_send.call_args_list[1][0][0]["body"]
        assert json.loads(body) == {"key": "value"}
