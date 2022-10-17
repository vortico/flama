import typing
import typing as t

from starlette import status

from flama import concurrency, exceptions, http, responses, websockets

if t.TYPE_CHECKING:
    from flama import asgi, http

__all__ = ["HTTPEndpoint", "WebSocketEndpoint"]


class HTTPEndpoint:
    def __init__(self, scope: "asgi.Scope", receive: "asgi.Receive", send: "asgi.Send") -> None:
        """An HTTP endpoint.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        """
        assert scope["type"] == "http"
        app = scope.get("app")
        route, route_scope = app.router.get_route_from_scope(scope)
        self.state = {
            "scope": scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "path_params": route_scope["path_params"],
            "route": route,
            "request": http.Request(scope, receive=receive),
        }

    def __await__(self) -> t.Generator:
        return self.dispatch().__await__()

    @property
    def allowed_methods(self) -> typing.List[str]:
        """The list of allowed methods by this endpoint.

        :return: List of allowed methods.
        """
        return [
            method
            for method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
            if getattr(self, method.lower(), None) is not None
        ]

    @property
    def handler(self) -> t.Callable:
        """The handler used for dispatching this request.

        :return: Handler.
        """
        handler_name = "get" if self.state["request"].method == "HEAD" else self.state["request"].method.lower()
        return getattr(self, handler_name, self.method_not_allowed)

    async def dispatch(self) -> None:
        """Dispatch a request.
        """
        app = self.state["app"]
        injected_func = await app.injector.inject(self.handler, self.state)
        return await concurrency.run(injected_func)

    async def method_not_allowed(self, request: "http.Request") -> "http.Response":
        """Handler for not allowed methods.

        If we're running inside a Flama application then raise an exception, so that the configurable exception handler
        can deal with returning the response. For plain ASGI apps, just return the response.

        :param request: Request.
        """
        headers = {"Allow": ", ".join(self.allowed_methods)}
        if self.state["app"]:
            raise exceptions.HTTPException(status_code=405, headers=headers)
        return responses.PlainTextResponse("Method Not Allowed", status_code=405, headers=headers)


class WebSocketEndpoint:
    encoding: typing.Optional[websockets.Encoding] = None  # May be "text", "bytes", or "json".

    def __init__(self, scope: "asgi.Scope", receive: "asgi.Receive", send: "asgi.Send") -> None:
        """A websocket endpoint.

        :param scope: ASGI scope.
        :param receive: ASGI receive function.
        :param send: ASGI send function.
        """
        assert scope["type"] == "websocket"
        app = scope.get("app")
        route, route_scope = app.router.get_route_from_scope(scope)
        self.state = {
            "scope": scope,
            "receive": receive,
            "send": send,
            "exc": None,
            "app": app,
            "path_params": route_scope["path_params"],
            "route": route,
            "websocket": websockets.WebSocket(scope, receive, send),
            "websocket_encoding": self.encoding,
            "websocket_code": websockets.Code(status.WS_1000_NORMAL_CLOSURE),
            "websocket_message": None,
        }

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    async def dispatch(self) -> None:
        """Dispatch a request.
        """
        app = self.state["app"]
        websocket = self.state["websocket"]

        on_connect = await app.injector.inject(self.on_connect, self.state)
        await on_connect()

        try:
            self.state["websocket_message"] = await websocket.receive()

            while websocket.client_state == websockets.WebSocketState.CONNECTED:
                on_receive = await app.injector.inject(self.on_receive, self.state)
                await on_receive()
                self.state["websocket_message"] = await websocket.receive()

            self.state["websocket_code"] = websockets.Code(
                int(self.state["websocket_message"].get("code", status.WS_1000_NORMAL_CLOSURE))
            )
        except exceptions.WebSocketException as e:
            self.state["websocket_code"] = websockets.Code(e.code)
        except Exception as e:
            self.state["websocket_code"] = websockets.Code(status.WS_1011_INTERNAL_ERROR)
            raise e from None
        finally:
            on_disconnect = await app.injector.inject(self.on_disconnect, self.state)
            await on_disconnect()

    async def on_connect(self, websocket: websockets.WebSocket) -> None:
        """Override to handle an incoming websocket connection.

        :param websocket: Websocket.
        """
        await websocket.accept()

    async def on_receive(self, websocket: websockets.WebSocket, data: websockets.Data) -> None:
        """Override to handle an incoming websocket message.

        :param websocket: Websocket.
        :param data: Received data.
        """

    async def on_disconnect(self, websocket: websockets.WebSocket, websocket_code: websockets.Code) -> None:
        """Override to handle a disconnecting websocket.

        :param websocket: Websocket.
        :param websocket_code: Websocket closing code.
        """
        await websocket.close(websocket_code)
