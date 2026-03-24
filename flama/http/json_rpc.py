import enum
import http
import typing as t

from flama.http.response import JSONResponse

__all__ = ["JSONRPC_VERSION", "JSONRPCStatus", "JSONRPCResponse", "JSONRPCErrorResponse"]

JSONRPC_VERSION = "2.0"


class JSONRPCStatus(enum.IntEnum):
    """JSON-RPC error codes as defined in https://www.jsonrpc.org/specification#error_object."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    @property
    def phrase(self) -> str:
        return self.name.replace("_", " ").capitalize()


class JSONRPCResponse(JSONResponse):
    version = JSONRPC_VERSION
    media_type = "application/json"

    def __init__(self, result: t.Any = None, *, id: str | int | None = None, **kwargs):
        self.result = result
        self.id = id
        super().__init__(
            {"jsonrpc": self.version, "id": id, "result": result}, status_code=http.HTTPStatus.OK, **kwargs
        )


class JSONRPCErrorResponse(JSONResponse):
    version = JSONRPC_VERSION
    media_type = "application/json"

    def __init__(self, *, status_code: int, message: str, data: t.Any = None, id: str | int | None = None, **kwargs):
        error = {"code": status_code, "message": message}
        if data is not None:
            error["data"] = data

        super().__init__({"jsonrpc": self.version, "id": id, "error": error}, status_code=http.HTTPStatus.OK, **kwargs)
