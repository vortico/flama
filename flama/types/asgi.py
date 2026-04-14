import typing as t

if t.TYPE_CHECKING:
    from flama import endpoints

__all__ = [
    "Scope",
    "Message",
    "Receive",
    "Send",
    "ASGIAppClass",
    "ASGIAppFunction",
    "ASGIApp",
    "HTTPHandler",
    "WebSocketHandler",
    "Handler",
]


class Scope(dict[str, t.Any]): ...


class Message(dict[str, t.Any]): ...


class Receive(t.Protocol):
    async def __call__(self) -> Message: ...


class Send(t.Protocol):
    async def __call__(self, message: Message) -> None: ...


# Applications
@t.runtime_checkable
class ASGIAppClass(t.Protocol):
    def __call__(self, scope: Scope, receive: Receive, send: Send) -> t.Awaitable[None]: ...


ASGIAppFunction = t.Callable[[Scope, Receive, Send], t.Awaitable[None]]
ASGIApp = ASGIAppClass | ASGIAppFunction


# Handlers
HTTPHandler = t.Callable[..., t.Any] | type["endpoints.HTTPEndpoint"]
WebSocketHandler = t.Callable[..., t.Any] | type["endpoints.WebSocketEndpoint"]
Handler = HTTPHandler | WebSocketHandler
