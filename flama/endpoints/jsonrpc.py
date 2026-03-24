import http as http_stdlib
import json
import logging
import typing as t

from flama import concurrency, exceptions, http, types
from flama.context import Context
from flama.endpoints.base import BaseEndpoint

__all__ = ["JSONRPCEndpoint"]

logger = logging.getLogger(__name__)


class JSONRPCEndpoint(BaseEndpoint, types.JSONRPCEndpointProtocol):
    """Base endpoint implementing JSON-RPC dispatch."""

    handlers: t.ClassVar[dict[str, str]] = {}

    def __init__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] != "http":
            raise ValueError("Wrong scope")

        super().__init__(scope, receive, send)

        self.state = Context(
            scope=self.state.scope,
            receive=self.state.receive,
            send=self.state.send,
            app=self.state.app,
            route=self.state.route,
            request=http.Request(scope, receive=receive),
        )

    def handler(self, method: str) -> t.Callable[..., t.Awaitable[t.Any] | t.Any]:
        if method == "dispatch":
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.METHOD_NOT_FOUND)

        handler_name = self.handlers.get(method)
        if handler_name is None:
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.METHOD_NOT_FOUND)

        handler = getattr(self, handler_name, None)
        if handler is None or not callable(handler):
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.METHOD_NOT_FOUND)

        return handler

    async def dispatch(self) -> t.Any:
        assert self.state.request is not None

        try:
            body = await self.state.request.json()
        except (json.JSONDecodeError, ValueError):
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.PARSE_ERROR)

        request_id = body.get("id")
        method = body.get("method")
        if body.get("jsonrpc") != http.JSONRPC_VERSION or not method:
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.INVALID_REQUEST, request_id=request_id)

        try:
            result = await concurrency.run(self.handler(method), **(body.get("params") or {}))
        except exceptions.JSONRPCException as e:
            e.request_id = request_id
            raise
        except Exception as e:
            logger.exception("Unhandled error in JSON-RPC method '%s'", method)
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, request_id=request_id, detail=str(e)
            ) from e

        if "id" not in body:
            response = http.Response(status_code=http_stdlib.HTTPStatus.ACCEPTED)
        else:
            response = http.JSONRPCResponse(result, id=request_id)

        return response
