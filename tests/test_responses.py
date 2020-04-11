import json
from unittest.mock import Mock, call, mock_open, patch

import pytest

from flama.exceptions import HTTPException, SerializationError
from flama.responses import APIErrorResponse, APIResponse, HTMLFileResponse


class TestCaseAPIResponse:
    @pytest.fixture
    def schema(self):
        return Mock()

    def test_init(self, schema):
        with patch("flama.responses.JSONResponse.__init__"):
            response = APIResponse(schema=schema)

        assert response.schema == schema

    def test_render(self, schema):
        content = {"foo": "bar"}
        expected_calls = [call(content)]
        expected_result = {"foo": "bar"}
        schema.dump.return_value = content

        response = APIResponse(schema=schema, content=content)

        assert schema.dump.call_args_list == expected_calls
        assert json.loads(response.body.decode()) == expected_result

    def test_render_no_content(self):
        content = {}
        expected_result = b""

        response = APIResponse(content=content)

        assert response.body == expected_result

    def test_render_no_schema(self):
        content = {"foo": "bar"}
        expected_result = {"foo": "bar"}

        response = APIResponse(content=content)

        assert json.loads(response.body.decode()) == expected_result

    def test_render_error(self, schema):
        content = {}
        expected_calls = [call(content)]
        schema.dump.side_effect = Exception

        with pytest.raises(SerializationError):
            APIResponse(schema=schema, content=content)

        assert schema.dump.call_args_list == expected_calls


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
