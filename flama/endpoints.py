from starlette import status
from starlette.endpoints import HTTPEndpoint as BaseHTTPEndpoint
from starlette.endpoints import WebSocketEndpoint as BaseWebSocketEndpoint
from starlette.requests import Request
from starlette.websockets import WebSocket, WebSocketState

from flama import exceptions, websockets
from flama.routing import prepare_http_request

__all__ = ["HTTPEndpoint", "WebSocketEndpoint"]


class HTTPEndpoint(BaseHTTPEndpoint):
    async def dispatch(self) -> None:
        request = Request(self.scope, receive=self.receive)
        app = self.scope["app"]

        route, route_scope = app.router.get_route_from_scope(self.scope)

        handler_name = "get" if request.method == "HEAD" else request.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        state = {
            "scope": self.scope,
            "receive": self.receive,
            "send": self.send,
            "exc": None,
            "app": app,
            "path_params": route_scope["path_params"],
            "route": route,
            "request": request,
        }

        response = await prepare_http_request(app, handler, state)
        await response(self.scope, self.receive, self.send)


class WebSocketEndpoint(BaseWebSocketEndpoint):
    async def dispatch(self) -> None:
        app = self.scope["app"]
        websocket = WebSocket(self.scope, self.receive, self.send)

        route, route_scope = app.router.get_route_from_scope(self.scope)

        state = {
            "scope": self.scope,
            "receive": self.receive,
            "send": self.send,
            "exc": None,
            "app": app,
            "path_params": route_scope["path_params"],
            "route": route,
            "websocket": websocket,
            "websocket_encoding": self.encoding,
            "websocket_code": status.WS_1000_NORMAL_CLOSURE,
            "websocket_message": None,
        }

        try:
            on_connect = await app.injector.inject(self.on_connect, state)
            await on_connect()
        except Exception as e:
            raise exceptions.WebSocketConnectionException("Error connecting socket") from e

        try:
            state["websocket_message"] = await websocket.receive()

            while websocket.client_state == WebSocketState.CONNECTED:
                on_receive = await app.injector.inject(self.on_receive, state)
                await on_receive()
                state["websocket_message"] = await websocket.receive()

            state["websocket_code"] = int(state["websocket_message"].get("code", status.WS_1000_NORMAL_CLOSURE))
        except exceptions.WebSocketException as e:
            state["websocket_code"] = e.close_code
        except Exception as e:
            state["websocket_code"] = status.WS_1011_INTERNAL_ERROR
            raise e from None
        finally:
            on_disconnect = await app.injector.inject(self.on_disconnect, state)
            await on_disconnect()

    async def on_connect(self, websocket: websockets.WebSocket) -> None:
        """Override to handle an incoming websocket connection"""
        await websocket.accept()

    async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data) -> None:
        """Override to handle an incoming websocket message"""

    async def on_disconnect(self, websocket: websockets.WebSocket, websocket_code: websockets.Code) -> None:
        """Override to handle a disconnecting websocket"""
        await websocket.close(websocket_code)
