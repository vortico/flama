import typing

from starlette.websockets import WebSocket, WebSocketClose, WebSocketDisconnect, WebSocketState

from flama.asgi import Message

__all__ = [
    "WebSocket",
    "WebSocketClose",
    "WebSocketState",
    "WebSocketDisconnect",
    "Message",
    "Code",
    "Encoding",
    "Data",
]


Code = typing.NewType("Code", int)
Encoding = typing.NewType("Encoding", str)
Data = typing.TypeVar("Data")
