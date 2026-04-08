import json

import pytest

from flama.http.responses.json_rpc import JSONRPCErrorResponse, JSONRPCResponse


class TestCaseJSONRPCResponse:
    def test_init(self):
        response = JSONRPCResponse(result={"data": "value"}, id=1)

        body = json.loads(response.body.decode())
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == 1
        assert body["result"] == {"data": "value"}

    def test_status_code(self):
        response = JSONRPCResponse(result=None, id=1)

        assert response.status_code == 200

    def test_media_type(self):
        response = JSONRPCResponse(result=None, id=1)

        assert response.headers["content-type"] == "application/json"


class TestCaseJSONRPCErrorResponse:
    @pytest.mark.parametrize(
        ["data", "has_data"],
        [
            pytest.param(None, False, id="without_data"),
            pytest.param({"info": "extra"}, True, id="with_data"),
        ],
    )
    def test_init(self, data, has_data):
        kwargs: dict = {"status_code": -32600, "message": "Invalid Request", "id": 1}
        if data is not None:
            kwargs["data"] = data

        response = JSONRPCErrorResponse(**kwargs)

        body = json.loads(response.body.decode())
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == 1
        assert body["error"]["code"] == -32600
        assert body["error"]["message"] == "Invalid Request"
        if has_data:
            assert body["error"]["data"] == data
        else:
            assert "data" not in body["error"]
