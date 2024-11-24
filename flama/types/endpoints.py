import typing as t

if t.TYPE_CHECKING:
    from flama import types, websockets

__all__ = ["EndpointProtocol", "HTTPEndpointProtocol", "WebSocketEndpointProtocol"]


class EndpointProtocol(t.Protocol):
    def __init__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        ...

    def __await__(self) -> t.Generator:
        ...

    @classmethod
    def allowed_handlers(cls) -> dict[str, t.Callable]:
        ...

    async def dispatch(self) -> None:
        ...


class HTTPEndpointProtocol(EndpointProtocol, t.Protocol):
    @classmethod
    def allowed_methods(cls) -> set[str]:
        ...

    @property
    def handler(self) -> t.Callable:
        ...


class WebSocketEndpointProtocol(EndpointProtocol, t.Protocol):
    encoding: t.Union["types.Encoding", None] = None

    async def on_connect(self, websocket: "websockets.WebSocket") -> None:
        ...

    async def on_receive(self, websocket: "websockets.WebSocket", data: "types.Data") -> None:
        ...

    async def on_disconnect(self, websocket: "websockets.WebSocket", websocket_code: "types.Code") -> None:
        ...
