import json

import pytest

from flama.http.responses.openapi import OpenAPIResponse


class TestCaseOpenAPIResponse:
    @pytest.mark.parametrize(
        ["test_input", "expected"],
        (
            pytest.param({"foo": "bar"}, {"foo": "bar"}, id="dict"),
            pytest.param("foo", "foo", id="string"),
        ),
    )
    def test_render(self, test_input, expected):
        response = OpenAPIResponse(test_input)

        assert json.loads(response.body.decode()) == expected
