import typing as t

import starlette.websockets

from flama import exceptions, types, websockets
from flama.endpoints.base import BaseEndpoint
from flama.endpoints.state import WebSocketEndpointState

__all__ = ["WebSocketEndpoint"]


class WebSocketEndpoint(BaseEndpoint, types.WebSocketEndpointProtocol):
    encoding: types.Encoding | None = None
    state: WebSocketEndpointState

    def __init__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        """A websocket endpoint.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        """
        if scope["type"] != "websocket":
            raise ValueError("Wrong scope")

        super().__init__(scope, receive, send)

        self.state = WebSocketEndpointState(
            scope=self.state.scope,
            receive=self.state.receive,
            send=self.state.send,
            app=self.state.app,
            route=self.state.route,
            websocket=websockets.WebSocket(self.state.scope, receive, send),
            websocket_encoding=self.encoding,
        )

    @classmethod
    def allowed_handlers(cls) -> dict[str, t.Callable]:
        """A mapping of handler related to each WS action.

        :return: Handlers mapping.
        """
        return {
            "WEBSOCKET_CONNECT": cls.on_connect,
            "WEBSOCKET_RECEIVE": cls.on_receive,
            "WEBSOCKET_DISCONNECT": cls.on_disconnect,
        }

    async def dispatch(self) -> None:
        """Dispatch a request."""
        app = self.state.app
        websocket = self.state.websocket

        on_connect = await app.injector.inject(self.on_connect, vars(self.state))
        await on_connect()

        try:
            self.state.websocket_message = t.cast(types.Message, await websocket.receive())

            while websocket.is_connected:
                on_receive = await app.injector.inject(self.on_receive, vars(self.state))
                await on_receive()
                self.state.websocket_message = t.cast(types.Message, await websocket.receive())

            if self.state.websocket_message is not None:
                self.state.websocket_code = types.Code(int(self.state.websocket_message.get("code", 1000)))
        except starlette.websockets.WebSocketDisconnect as e:
            self.state.websocket_code = types.Code(e.code)
            raise exceptions.WebSocketException(e.code, e.reason) from None
        except exceptions.WebSocketException as e:
            self.state.websocket_code = types.Code(e.code)
            raise e from None
        except Exception as e:
            self.state.websocket_code = types.Code(1011)
            raise e from None
        finally:
            on_disconnect = await app.injector.inject(self.on_disconnect, vars(self.state))
            await on_disconnect()

    async def on_connect(self, websocket: websockets.WebSocket, *args, **kwargs) -> None:
        """Handle an incoming websocket connection.

        :param websocket: Websocket.
        """
        await websocket.accept()

    async def on_receive(self, websocket: websockets.WebSocket, data: types.Data, *args, **kwargs) -> None:
        """Handle an incoming websocket message.

        :param websocket: Websocket.
        :param data: Received data.
        """
        ...

    async def on_disconnect(self, websocket: websockets.WebSocket, websocket_code: types.Code, *args, **kwargs) -> None:
        """Handle a disconnecting websocket.

        :param websocket: Websocket.
        :param websocket_code: Websocket closing code.
        """
        await websocket.close(websocket_code)
