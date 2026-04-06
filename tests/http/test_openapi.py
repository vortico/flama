import json
from unittest.mock import AsyncMock, call, patch

import pytest

from flama import types
from flama.http.openapi import OpenAPIResponse


class TestCaseOpenAPIResponse:
    @pytest.mark.parametrize(
        "test_input,expected,exception",
        (
            pytest.param({"foo": "bar"}, {"foo": "bar"}, None, id="success"),
            pytest.param("foo", None, ValueError("The schema must be a dictionary"), id="wrong_content"),
        ),
        indirect=("exception",),
    )
    def test_render(self, test_input, expected, exception):
        with exception:
            response = OpenAPIResponse(test_input)

            assert json.loads(response.body.decode()) == expected

    async def test_call(self):
        response = OpenAPIResponse(content={})
        scope, receive, send = types.Scope({}), AsyncMock(), AsyncMock()

        with patch("starlette.schemas.OpenAPIResponse.__call__") as call_mock:
            await response(scope, receive, send)

            assert call_mock.call_args_list == [call(scope, receive, send)]
