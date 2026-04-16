import http
import typing as t

from flama.http.data_structures import JSONRPC_VERSION
from flama.http.responses.json import JSONResponse

__all__ = ["JSONRPCResponse", "JSONRPCErrorResponse"]


class JSONRPCResponse(JSONResponse):
    version = JSONRPC_VERSION

    def __init__(self, result: t.Any = None, *, id: str | int | None = None, **kwargs):
        self.result = result
        self.id = id
        super().__init__(
            {"jsonrpc": self.version, "id": id, "result": result}, status_code=http.HTTPStatus.OK, **kwargs
        )


class JSONRPCErrorResponse(JSONResponse):
    version = JSONRPC_VERSION

    def __init__(self, *, status_code: int, message: str, data: t.Any = None, id: str | int | None = None, **kwargs):
        error = {"code": status_code, "message": message}
        if data is not None:
            error["data"] = data

        super().__init__({"jsonrpc": self.version, "id": id, "error": error}, status_code=http.HTTPStatus.OK, **kwargs)
