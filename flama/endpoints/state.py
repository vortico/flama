import dataclasses
import typing as t

from flama import types

if t.TYPE_CHECKING:
    from flama import Flama, http, websockets
    from flama.routing import BaseRoute

__all__ = ["BaseEndpointState", "HTTPEndpointState", "WebSocketEndpointState"]


@dataclasses.dataclass
class BaseEndpointState:
    scope: types.Scope
    receive: types.Receive
    send: types.Send
    app: "Flama"
    route: "BaseRoute"
    exc: Exception | None = None


@dataclasses.dataclass(kw_only=True)
class HTTPEndpointState(BaseEndpointState):
    request: "http.Request"


@dataclasses.dataclass(kw_only=True)
class WebSocketEndpointState(BaseEndpointState):
    websocket: "websockets.WebSocket"
    websocket_encoding: types.Encoding | None = None
    websocket_code: types.Code | None = None
    websocket_message: types.Message | None = None
