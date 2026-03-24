import pytest

from flama.exceptions import JSONRPCException
from flama.http import JSONRPCStatus


class TestCaseJSONRPCStatus:
    @pytest.mark.parametrize(
        ["member", "value", "phrase"],
        (
            pytest.param(JSONRPCStatus.PARSE_ERROR, -32700, "Parse error", id="parse_error"),
            pytest.param(JSONRPCStatus.INVALID_REQUEST, -32600, "Invalid request", id="invalid_request"),
            pytest.param(JSONRPCStatus.METHOD_NOT_FOUND, -32601, "Method not found", id="method_not_found"),
            pytest.param(JSONRPCStatus.INVALID_PARAMS, -32602, "Invalid params", id="invalid_params"),
            pytest.param(JSONRPCStatus.INTERNAL_ERROR, -32603, "Internal error", id="internal_error"),
        ),
    )
    def test_value(self, member, value, phrase):
        assert member == value
        assert member.phrase == phrase

    @pytest.mark.parametrize(
        ["value", "phrase"],
        (
            pytest.param(-32700, "Parse error", id="parse_error"),
            pytest.param(-32600, "Invalid request", id="invalid_request"),
            pytest.param(-32601, "Method not found", id="method_not_found"),
            pytest.param(-32602, "Invalid params", id="invalid_params"),
            pytest.param(-32603, "Internal error", id="internal_error"),
        ),
    )
    def test_lookup(self, value, phrase):
        status = JSONRPCStatus(value)
        assert status.phrase == phrase


class TestCaseJSONRPCException:
    @pytest.mark.parametrize(
        ["status_code", "detail", "expected_detail"],
        (
            pytest.param(-32603, None, "Internal error", id="default_detail"),
            pytest.param(-32603, "custom", "custom", id="custom_detail"),
            pytest.param(-32700, None, "Parse error", id="parse_error_default"),
        ),
    )
    def test_init(self, status_code, detail, expected_detail):
        error = JSONRPCException(status_code, detail=detail)
        assert error.status_code == status_code
        assert error.detail == expected_detail

    def test_str(self):
        assert str(JSONRPCException(-32603)) == "Internal error"
        assert str(JSONRPCException(-32603, detail="boom")) == "boom"

    def test_repr(self):
        assert repr(JSONRPCException(-32603, detail="boom")) == "JSONRPCException(status_code=-32603, detail='boom')"

    @pytest.mark.parametrize(
        ["a", "b", "expected"],
        (
            pytest.param(JSONRPCException(-32603), JSONRPCException(-32603), True, id="equal"),
            pytest.param(JSONRPCException(-32603), JSONRPCException(-32700), False, id="different_code"),
            pytest.param(
                JSONRPCException(-32603, detail="a"), JSONRPCException(-32603, detail="b"), False, id="different_detail"
            ),
            pytest.param(JSONRPCException(-32603), "not an error", False, id="different_type"),
        ),
    )
    def test_eq(self, a, b, expected):
        assert (a == b) is expected
