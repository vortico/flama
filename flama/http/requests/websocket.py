import json
import typing as t

from flama import exceptions, types
from flama._core.json_encoder import encode_json
from flama.http.data_structures import WebSocketStatus
from flama.http.requests.connection import HTTPConnection

if t.TYPE_CHECKING:
    from collections.abc import Iterable

    from flama.http.responses.response import Response

__all__ = ["WebSocket", "WebSocketClose"]


class WebSocket(HTTPConnection):
    """An ASGI WebSocket connection.

    Wraps the raw ASGI ``receive`` / ``send`` callables with a state machine that
    validates protocol transitions and exposes typed send/receive helpers.

    :param scope: ASGI connection scope (must have ``type == "websocket"``).
    :param receive: ASGI receive callable.
    :param send: ASGI send callable.
    """

    def __init__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        super().__init__(scope)
        self._receive = receive
        self._send = send
        self.client_status = WebSocketStatus.CONNECTING
        self.application_status = WebSocketStatus.CONNECTING

    @t.overload
    async def receive(self, *, data: None = None) -> types.Message: ...
    @t.overload
    async def receive(self, *, data: t.Literal["bytes"] | None = None) -> bytes | str | types.JSONSchema: ...
    @t.overload
    async def receive(self, *, data: t.Literal["text"]) -> str: ...
    @t.overload
    async def receive(self, *, data: t.Literal["json"]) -> types.JSONSchema: ...
    async def receive(
        self, *, data: t.Literal["bytes", "text", "json"] | None = None
    ) -> types.Message | bytes | str | types.JSONSchema:
        """Receive an ASGI WebSocket message, enforcing valid client state transitions.

        :param data: Data type to parse.
        :return: The received ASGI message.
        :raises RuntimeError: On invalid state or unexpected message type.
        :raises WebSocketDisconnect: If the client disconnects.
        """
        if self.client_status == WebSocketStatus.DISCONNECTED:
            raise RuntimeError('Cannot call "receive" once a disconnect message has been received.')

        message = await self._receive()
        message_type = message["type"]

        if self.client_status == WebSocketStatus.CONNECTING:
            if message_type != "websocket.connect":
                raise RuntimeError(f'Expected ASGI message "websocket.connect", but got {message_type!r}')
            self.client_status = WebSocketStatus.CONNECTED
            return message

        if message_type not in ("websocket.receive", "websocket.disconnect"):
            raise RuntimeError(
                f'Expected ASGI message "websocket.receive" or "websocket.disconnect", but got {message_type!r}'
            )
        elif message_type == "websocket.disconnect":
            self.client_status = WebSocketStatus.DISCONNECTED
            raise exceptions.WebSocketDisconnect(message["code"], message.get("reason"))

        match data:
            case "bytes":
                result = t.cast(bytes, message["bytes"])
            case "text":
                result = t.cast(str, message["text"])
            case "json":
                result = t.cast(types.JSONSchema, json.loads(message["bytes"]))
            case None:
                result = message

        return result

    @t.overload
    async def send(self, *, message: types.Message) -> None: ...
    @t.overload
    async def send(self, *, data: bytes | str) -> None: ...
    @t.overload
    async def send(self, *, json: types.JSONSchema) -> None: ...
    async def send(
        self,
        *,
        message: types.Message | None = None,
        data: bytes | str | None = None,
        json: types.JSONSchema | None = None,
    ) -> None:
        """Send an ASGI WebSocket message, enforcing valid application state transitions.

        :param message: The ASGI message to send.
        :raises ValueError: On unexpected message type.
        :raises RuntimeError: On invalid state.
        :raises WebSocketDisconnect: If the client disconnects.
        """
        if message is None:
            message = types.Message({"type": "websocket.send"})
            if data is None and json is None:
                raise ValueError("Either 'data', 'message' or 'json' must be provided")
            elif json is not None:
                message["text"] = encode_json(json).decode()
            elif data is not None:
                message["bytes" if isinstance(data, bytes) else "text"] = data
            else:
                raise ValueError("Parameters 'data', 'message' and 'json' are mutually exclusive")
        elif data is not None or json is not None:
            raise ValueError("Parameters 'data', 'message' and 'json' are mutually exclusive")

        match self.application_status:
            case WebSocketStatus.CONNECTING:
                await self._send_connecting(message)
            case WebSocketStatus.CONNECTED:
                await self._send_connected(message)
            case WebSocketStatus.RESPONSE:
                await self._send_response(message)
            case _:
                raise RuntimeError('Cannot call "send" once a close message has been sent.')

    async def _send_connecting(self, message: types.Message) -> None:
        message_type = message["type"]
        if message_type not in {"websocket.accept", "websocket.close", "websocket.http.response.start"}:
            raise RuntimeError(
                'Expected ASGI message "websocket.accept", "websocket.close" or '
                f'"websocket.http.response.start", but got {message_type!r}'
            )
        if message_type == "websocket.close":
            self.application_status = WebSocketStatus.DISCONNECTED
        elif message_type == "websocket.http.response.start":
            self.application_status = WebSocketStatus.RESPONSE
        else:
            self.application_status = WebSocketStatus.CONNECTED
        await self._send(message)

    async def _send_connected(self, message: types.Message) -> None:
        message_type = message["type"]
        if message_type not in {"websocket.send", "websocket.close"}:
            raise RuntimeError(f'Expected ASGI message "websocket.send" or "websocket.close", but got {message_type!r}')
        if message_type == "websocket.close":
            self.application_status = WebSocketStatus.DISCONNECTED
        try:
            await self._send(message)
        except OSError:
            self.application_status = WebSocketStatus.DISCONNECTED
            raise exceptions.WebSocketDisconnect(code=1006)

    async def _send_response(self, message: types.Message) -> None:
        message_type = message["type"]
        if message_type != "websocket.http.response.body":
            raise RuntimeError(f'Expected ASGI message "websocket.http.response.body", but got {message_type!r}')
        if not message.get("more_body", False):
            self.application_status = WebSocketStatus.DISCONNECTED
        await self._send(message)

    async def accept(
        self, subprotocol: str | None = None, headers: "Iterable[tuple[bytes, bytes]] | None" = None
    ) -> None:
        """Accept the WebSocket connection.

        If the ``websocket.connect`` message has not yet been received, it is
        consumed automatically before sending the accept.

        :param subprotocol: Optional subprotocol to negotiate.
        :param headers: Optional extra headers to include in the accept message.
        """
        if self.client_status == WebSocketStatus.CONNECTING:
            await self.receive()
        await self.send(
            message=types.Message(
                {"type": "websocket.accept", "subprotocol": subprotocol, "headers": list(headers or [])}
            )
        )

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        """Send a close frame.

        :param code: WebSocket close code.
        :param reason: Human-readable reason.
        """
        await self.send(message=types.Message({"type": "websocket.close", "code": code, "reason": reason or ""}))

    async def send_denial_response(self, response: "Response") -> None:
        """Send an HTTP denial response via the WebSocket Denial Response extension.

        :param response: The HTTP response to send.
        :raises RuntimeError: If the server does not support the extension.
        """
        if "websocket.http.response" in self.scope.get("extensions", {}):
            await response(self.scope, self._receive, self._send)
        else:
            raise RuntimeError("The server doesn't support the Websocket Denial Response extension.")

    @property
    def is_connecting(self) -> bool:
        """Check if websocket is connecting.

        :return: True if connecting.
        """
        return self.client_status == WebSocketStatus.CONNECTING

    @property
    def is_connected(self) -> bool:
        """Check if websocket is connected.

        :return: True if connected.
        """
        return self.client_status == WebSocketStatus.CONNECTED

    @property
    def is_disconnected(self) -> bool:
        """Check if websocket is disconnected.

        :return: True if disconnected.
        """
        return self.client_status == WebSocketStatus.DISCONNECTED


class WebSocketClose:
    """ASGI application that immediately closes a WebSocket connection.

    :param code: WebSocket close code.
    :param reason: Human-readable close reason.
    """

    def __init__(self, code: int = 1000, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason or ""

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await send(types.Message({"type": "websocket.close", "code": self.code, "reason": self.reason}))
