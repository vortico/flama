import uuid

from flama import concurrency, types
from flama.http.data_structures import Headers, MutableHeaders
from flama.middleware.base import Middleware

__all__ = ["CorrelationIdMiddleware"]


class CorrelationIdMiddleware(Middleware):
    """ASGI middleware that assigns a unique identifier to every request.

    Propagates an existing ID from the incoming request header, or generates a new UUID4 if absent.  The ID is stored
    in ``scope["correlation_id"]`` for downstream middleware and handlers, and emitted as a response header.

    :param header: Header name used to read and write the request ID.
    """

    def __init__(self, header: str = "X-Correlation-Id") -> None:
        self._header = header.lower()

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await concurrency.run(self.app, scope, receive, send)
            return

        correlation_id = Headers(scope=scope).get(self._header) or uuid.uuid4().hex
        scope["correlation_id"] = correlation_id

        async def _send(message: types.Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append(self._header, correlation_id)

            await send(message)

        await concurrency.run(self.app, scope, receive, _send)
