import datetime
import json
from unittest.mock import Mock, mock_open, patch

import pytest
from pytest import param

from flama import schemas
from flama.exceptions import HTTPException, SerializationError
from flama.responses import APIErrorResponse, APIResponse, HTMLFileResponse, JSONResponse, OpenAPIResponse


class TestCaseJSONResponse:
    @pytest.fixture
    def schema(self):
        return Mock()

    def test_render(self, schema):  # TODO: do
        content = {"foo": datetime.timedelta(days=1, hours=20, minutes=30, seconds=10, milliseconds=10, microseconds=6)}
        expected_result = {"foo": "P1D20H30M10.010006S"}

        response = JSONResponse(content=content)

        assert json.loads(response.body.decode()) == expected_result


class TestCaseAPIResponse:
    @pytest.fixture
    def schema(self):
        return Mock()

    def test_init(self, schema):
        with patch("flama.responses.JSONResponse.__init__"):
            response = APIResponse(schema=schema)

        assert response.schema == schema

    @pytest.mark.parametrize(
        "schema,content,expected,exception",
        (
            param(Mock(return_value={"foo": "bar"}), {"foo": "bar"}, '{"foo":"bar"}', None, id="schema_and_content"),
            param(None, {}, "", None, id="no_content"),
            param(None, {"foo": "bar"}, '{"foo":"bar"}', None, id="no_schema"),
            param(Mock(side_effect=schemas.SchemaValidationError(errors={})), {}, "", SerializationError, id="error"),
        ),
        indirect=("exception",),
    )
    def test_render(self, schema, content, expected, exception):
        with patch.object(schemas.adapter, "dump", new=schema), exception:
            response = APIResponse(schema=schema, content=content)
            assert response.body.decode() == expected


class TestCaseAPIErrorResponse:
    def test_init(self):
        detail = "foo"
        exception = ValueError()
        status_code = 401
        expected_result = {"detail": "foo", "error": "ValueError", "status_code": 401}

        response = APIErrorResponse(detail=detail, status_code=status_code, exception=exception)

        assert response.detail == detail
        assert response.exception == exception
        assert response.status_code == status_code
        assert json.loads(response.body.decode()) == expected_result


class TestCaseHTMLFileResponse:
    def test_init(self):
        content = "<html></html>"
        with patch("builtins.open", mock_open(read_data=content)):
            response = HTMLFileResponse("foo.html")

        assert response.body == content.encode()

    def test_init_error(self):
        error_detail = "Foo error"
        with patch("builtins.open", side_effect=ValueError(error_detail)), pytest.raises(HTTPException) as exc:
            HTMLFileResponse("foo.html")

            assert exc.status_code == 500
            assert exc.detail == error_detail


class TestCaseOpenAPIResponse:
    @pytest.mark.parametrize(
        "test_input,expected,exception",
        (
            param({"foo": "bar"}, {"foo": "bar"}, None, id="success"),
            param("foo", None, AssertionError, id="wrong_content"),
        ),
        indirect=("exception",),
    )
    def test_render(self, test_input, expected, exception):
        with exception:
            response = OpenAPIResponse(test_input)

            assert json.loads(response.body.decode()) == expected
