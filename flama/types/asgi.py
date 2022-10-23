import typing as t

if t.TYPE_CHECKING:
    from flama import endpoints

__all__ = ["Scope", "Message", "Receive", "Send", "AppClass", "AppFunction", "App", "HTTPHandler", "WebSocketHandler"]


Scope = t.NewType("Scope", t.MutableMapping[str, t.Any])
Message = t.NewType("Message", t.MutableMapping[str, t.Any])


class Receive(t.Protocol):
    async def __call__(self) -> Message:
        ...


class Send(t.Protocol):
    async def __call__(self, message: Message) -> None:
        ...


class AppClass(t.Protocol):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ...


AppFunction = t.Callable
App = t.Union[AppClass, AppFunction]

HTTPHandler = t.Union[AppFunction, "endpoints.HTTPEndpoint", t.Type["endpoints.HTTPEndpoint"]]
WebSocketHandler = t.Union[AppFunction, "endpoints.WebSocketEndpoint", t.Type["endpoints.WebSocketEndpoint"]]
