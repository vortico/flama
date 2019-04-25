import asyncio
import typing

from starlette import status
from starlette.concurrency import run_in_threadpool
from starlette.endpoints import HTTPEndpoint as BaseHTTPEndpoint
from starlette.endpoints import WebSocketEndpoint as BaseWebSocketEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Send
from starlette.websockets import WebSocket, WebSocketState

from flama import exceptions, websockets
from flama.responses import APIResponse
from flama.validation import get_output_schema

__all__ = ["HTTPEndpoint", "WebSocketEndpoint"]


class HTTPEndpoint(BaseHTTPEndpoint):
    async def __call__(self, receive: Receive, send: Send):
        request = Request(self.scope, receive=receive)
        app = self.scope["app"]
        kwargs = self.scope.get("kwargs", {})

        route, route_scope = app.router.get_route_from_scope(self.scope)

        state = {
            "scope": self.scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "path_params": route_scope["path_params"],
            "route": route,
            "request": request,
        }
        response = await self.dispatch(request, state, **kwargs)

        return await response(receive, send)

    async def dispatch(self, request: Request, state: typing.Dict, **kwargs) -> Response:
        handler_name = "get" if request.method == "HEAD" else request.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        app = state["app"]
        injected_func = await app.injector.inject(handler, state)
        if asyncio.iscoroutinefunction(handler):
            response = await injected_func()
        else:
            response = await run_in_threadpool(injected_func)

        # Wrap response data with a proper response class
        if isinstance(response, (dict, list)):
            response = APIResponse(content=response, schema=get_output_schema(handler))
        elif isinstance(response, str):
            response = APIResponse(content=response)
        elif response is None:
            response = APIResponse(content="")

        return response


class WebSocketEndpoint(BaseWebSocketEndpoint):
    async def __call__(self, receive: Receive, send: Send) -> None:
        app = self.scope["app"]
        websocket = WebSocket(self.scope, receive, send)

        route, route_scope = app.router.get_route_from_scope(self.scope)

        state = {
            "scope": self.scope,
            "receive": receive,
            "send": send,
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
