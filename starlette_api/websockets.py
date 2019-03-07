import typing

from starlette.websockets import Message, WebSocket

__all__ = ["WebSocket", "Message", "Code", "Encoding", "Data"]


Code = typing.NewType("Code", int)
Encoding = typing.NewType("Encoding", str)
Data = typing.TypeVar("Data")
