
import starlette.websockets

from flama.types.asgi import Receive, Scope, Send

__all__ = ["WebSocket", "Close", "State"]

State = starlette.websockets.WebSocketState


class WebSocket(starlette.websockets.WebSocket):
    def __init__(self, scope: Scope, receive: Receive, send: Send):
        super().__init__(scope, receive, send)  # ty: ignore[invalid-argument-type]

    @property
    def is_connecting(self) -> bool:
        """Check if websocket is connecting.

        :return: True if connecting.
        """
        return self.client_state == starlette.websockets.WebSocketState.CONNECTING

    @property
    def is_connected(self) -> bool:
        """Check if websocket is connected.

        :return: True if connected.
        """
        return self.client_state == starlette.websockets.WebSocketState.CONNECTED

    @property
    def is_disconnected(self) -> bool:
        """Check if websocket is disconnected.

        :return: True if disconnected.
        """
        return self.client_state == starlette.websockets.WebSocketState.DISCONNECTED


class Close(starlette.websockets.WebSocketClose):
    async def __call__(  # ty: ignore[invalid-method-override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        await super().__call__(scope, receive, send)  # ty: ignore[invalid-argument-type]
