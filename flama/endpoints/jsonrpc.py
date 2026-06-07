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
    """Base endpoint implementing JSON-RPC dispatch through dependency injection.

    The request envelope, method name, and params are derived from the request by the application injector
    (see :mod:`flama.endpoints.components`), so handlers can declare them as typed dependencies.
    """

    handlers: t.ClassVar[dict[str, str]] = {}

    scope_type = "http"
    state: Context

    def build_context(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> dict[str, t.Any]:
        """Build the JSON-RPC-specific context fields.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        :return: Mapping with the request bound to this endpoint.
        """
        return {"request": http.Request(scope, receive=receive)}

    @classmethod
    def allowed_handlers(cls) -> dict[str, t.Callable[..., t.Awaitable[t.Any] | t.Any]]:
        """A mapping of handler related to each JSON-RPC method.

        :return: Handlers mapping.
        """
        return {method: getattr(cls, handler_name) for method, handler_name in cls.handlers.items()}

    async def resolve_handler(self) -> t.Callable[..., t.Awaitable[t.Any] | t.Any]:
        """Resolve the callable handler bound to the current JSON-RPC method.

        :return: Handler.
        """
        method = await self.state.app.injector.value(types.JSONRPCMethod, self.state)

        if not method or method == "dispatch":
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.METHOD_NOT_FOUND)

        if (handler_name := self.handlers.get(method)) is None:
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.METHOD_NOT_FOUND)

        if (handler := getattr(self, handler_name, None)) is None or not callable(handler):
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.METHOD_NOT_FOUND)

        return handler

    async def dispatch(self) -> t.Any:
        app = self.state.app

        try:
            envelope = await app.injector.value(types.JSONRPCEnvelope, self.state)
        except (json.JSONDecodeError, ValueError):
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.PARSE_ERROR)

        request_id = envelope.get("id")
        if envelope.get("jsonrpc") != http.JSONRPC_VERSION or not envelope.get("method"):
            raise exceptions.JSONRPCException(status_code=http.JSONRPCStatus.INVALID_REQUEST, request_id=request_id)

        try:
            handler = await self.resolve_handler()
            result = await concurrency.run(await app.injector.inject(handler, self.state))
        except exceptions.JSONRPCException as e:
            e.request_id = request_id
            raise
        except Exception as e:
            logger.exception("Unhandled error in JSON-RPC method '%s'", envelope.get("method"))
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, request_id=request_id, detail=str(e)
            ) from e

        if "id" not in envelope:
            return http.PlainTextResponse("", status_code=http_stdlib.HTTPStatus.ACCEPTED)

        return http.JSONRPCResponse(result, id=request_id)
