import sys
import typing as t

if sys.version_info >= (3, 8):  # PORT: Remove when stop supporting 3.8 # pragma: no cover
    from typing import Protocol
else:  # pragma: no cover
    from typing_extensions import Protocol

if t.TYPE_CHECKING:
    from flama import endpoints

__all__ = ["Scope", "Message", "Receive", "Send", "AppClass", "AppFunction", "App", "HTTPHandler", "WebSocketHandler"]


Scope = t.NewType("Scope", t.MutableMapping[str, t.Any])
Message = t.NewType("Message", t.MutableMapping[str, t.Any])


class Receive(Protocol):
    async def __call__(self) -> Message:
        ...


class Send(Protocol):
    async def __call__(self, message: Message) -> None:
        ...


class AppClass(Protocol):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ...


AppFunction = t.Callable
App = t.Union[AppClass, AppFunction]

HTTPHandler = t.Union[AppFunction, "endpoints.HTTPEndpoint", t.Type["endpoints.HTTPEndpoint"]]
WebSocketHandler = t.Union[AppFunction, "endpoints.WebSocketEndpoint", t.Type["endpoints.WebSocketEndpoint"]]
