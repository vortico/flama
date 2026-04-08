import json

import pytest

from flama.http.responses.openapi import OpenAPIResponse


class TestCaseOpenAPIResponse:
    @pytest.mark.parametrize(
        ["test_input", "expected", "exception"],
        (
            pytest.param({"foo": "bar"}, {"foo": "bar"}, None, id="success"),
            pytest.param("foo", None, ValueError("The schema must be a dictionary"), id="wrong_content"),
        ),
        indirect=["exception"],
    )
    def test_render(self, test_input, expected, exception):
        with exception:
            response = OpenAPIResponse(test_input)

            assert json.loads(response.body.decode()) == expected
